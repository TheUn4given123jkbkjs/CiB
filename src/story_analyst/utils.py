import uuid
import google.generativeai as genai
import os
import re
import json
import time
import urllib.request
import urllib.error
from typing import Optional, Any

_api_configured = False
_api_key = ""
_model_name = ""
_api_url = ""

class QuotaLimitReachedException(Exception):
    """Exception raised when API quota is exceeded after multiple retries."""
    pass

def configure_api_generic(api_key: str, model_name: str, api_url: str = ""):
    """Configures the generic API variables globally."""
    global _api_configured, _api_key, _model_name, _api_url
    _api_key = api_key
    _model_name = model_name
    _api_url = api_url
    
    if not api_url and api_key:
        genai.configure(api_key=api_key)
        
    _api_configured = True

def configure_api(api_key: str):
    """Configures the API key globally (backward compatible)."""
    configure_api_generic(api_key, os.environ.get("MODEL_NAME", "gemini-2.5-flash"))

def generate_id(prefix: str) -> str:
    """Generates a unique structured ID using a prefix and a short UUID hash."""
    unique_suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{unique_suffix}"

def parse_json_response(text: str) -> Any:
    """
    Cleans and robustly parses a JSON string returned by the LLM.
    Handles markdown code fences, leading/trailing conversational text,
    and common syntax glitches.
    """
    if not text:
        return {}
        
    text = text.strip()
    
    # 1. Remove markdown code fences if present (e.g. ```json ... ```)
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    # 2. Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # 3. Use regex to extract the first valid JSON object or array block
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        extracted = match.group(1).strip()
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            # 4. Repair unescaped newlines within double-quoted string values
            try:
                repaired = re.sub(
                    r'(?<=[:,\s\[{])"([^"\\]*(?:\\.[^"\\]*)*)"',
                    lambda m: m.group(0).replace('\n', '\\n'),
                    extracted
                )
                return json.loads(repaired)
            except Exception:
                pass
                
    # If all parsing attempts fail, raise the parse exception so the caller knows
    raise ValueError(f"Could not parse valid JSON from LLM output: {text[:200]}...")

def call_openai_compatible_api(prompt: str, system_instruction: Optional[str], json_mode: bool, api_key: str, model_name: str, api_url: str) -> str:
    """Sends a request to an OpenAI-compatible chat completion endpoint (e.g. Groq, OpenRouter, local server)."""
    # Construct messages array
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1
    }
    
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(api_url, data=data)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    max_retries = 3
    base_delay = 5.0
    
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            err_code = e.code
            err_content = e.read().decode("utf-8")
            print(f"[API HTTP Error - Attempt {attempt+1}/{max_retries+1}]: Code {err_code}, Details: {err_content}", flush=True)
            
            if err_code == 429:
                if attempt < max_retries:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"Rate Limit hit. Sleeping for {sleep_time:.2f} seconds before retrying...", flush=True)
                    time.sleep(sleep_time)
                    continue
                else:
                    raise QuotaLimitReachedException(f"API Quota Exceeded: {err_content}")
            
            return "{}" if json_mode else f"HTTP Error {err_code}"
        except Exception as e:
            print(f"[API Error]: {e}", flush=True)
            return "{}" if json_mode else f"Error: {e}"
            
    raise QuotaLimitReachedException("API Quota Exceeded. Max retries exhausted.")

def load_generic_config():
    """Dynamically parses and syncs API_KEY, MODEL_NAME, and API_URL from .env to support runtime updates."""
    global _api_configured, _api_key, _model_name, _api_url
    
    env_vars = {}
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        env_path = os.path.join(current_dir, ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            key_name = k.strip()
                            val = v.strip().strip("'\"")
                            if key_name not in env_vars:
                                env_vars[key_name] = val
            except Exception:
                pass
        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            break
        current_dir = parent

    # Override/Sync os.environ with active keys
    for k, v in env_vars.items():
        os.environ[k] = v

    # Delete commented-out variables to support dynamic fallback without restarting
    for key in ["API_KEY", "MODEL_NAME", "API_URL"]:
        if key not in env_vars and key in os.environ:
            del os.environ[key]

    api_key = os.environ.get("API_KEY")
    model_name = os.environ.get("MODEL_NAME")
    api_url = os.environ.get("API_URL", "")

    if api_key:
        if not _api_configured or api_key != _api_key or model_name != _model_name or api_url != _api_url:
            configure_api_generic(api_key, model_name, api_url)
    else:
        _api_configured = False
        _api_key = ""
        _model_name = ""
        _api_url = ""

def call_llm(prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False) -> str:
    """
    Sends a generation request to either native Gemini SDK or OpenAI-compatible endpoint.
    Automatically configures itself based on API_KEY, MODEL_NAME, and API_URL in the environment/.env file.
    """
    global _api_configured, _api_key, _model_name, _api_url
    
    load_generic_config()
    
    if not _api_configured or not _api_key:
        return "{}" if json_mode else "Fallback LLM output."

    # If API_URL is specified, route to the OpenAI-compatible custom endpoint (e.g. Groq)
    if _api_url:
        return call_openai_compatible_api(prompt, system_instruction, json_mode, _api_key, _model_name, _api_url)

    generation_config = {}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    max_retries = 3
    base_delay = 12.0

    for attempt in range(max_retries + 1):
        try:
            model = genai.GenerativeModel(
                model_name=_model_name or "gemini-2.5-flash",
                generation_config=generation_config,
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            err_msg = str(e)
            print(f"[LLM Error - Attempt {attempt + 1}/{max_retries + 1}]: {e}", flush=True)
            
            # Catch rate limits and quota exceeded errors
            if "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
                if attempt < max_retries:
                    sleep_time = base_delay * (1.5 ** attempt)
                    print(f"Rate limit / Free Tier quota hit. Sleeping for {sleep_time:.2f} seconds before retrying...", flush=True)
                    time.sleep(sleep_time)
                    continue
                else:
                    raise QuotaLimitReachedException("Gemini API Quota Exceeded. Max retries exhausted.")
            
            return "{}" if json_mode else f"Error call_llm: {e}"

    raise QuotaLimitReachedException("Gemini API Quota Exceeded. Max retries exhausted.")
