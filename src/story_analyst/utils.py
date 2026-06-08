import uuid
import google.generativeai as genai
import os
import re
import json
import time
import urllib.request
import urllib.error
import socket
from typing import Optional, Any

_api_configured = False
_api_key = ""
_model_name = ""
_api_url = ""

_complex_api_configured = False
_complex_api_key = ""
_complex_model_name = ""
_complex_api_url = ""

_token_stats = {
    "total_requests": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "local_requests": 0,
    "local_input_tokens": 0,
    "local_output_tokens": 0,
    "remote_requests": 0,
    "remote_input_tokens": 0,
    "remote_output_tokens": 0
}

def get_token_stats() -> dict:
    """Returns the current token and request usage statistics."""
    global _token_stats
    return _token_stats.copy()

def reset_token_stats():
    """Resets the token and request usage statistics to zero."""
    global _token_stats
    for k in _token_stats:
        _token_stats[k] = 0

class QuotaLimitReachedException(Exception):
    """Exception raised when API quota is exceeded after multiple retries."""
    pass

class OllamaConnectionException(Exception):
    """Exception raised when local Ollama server is unreachable or times out."""
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
    global _token_stats
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
    
    # Read timeout and attempts configuration from environment
    try:
        api_timeout = int(os.environ.get("API_TIMEOUT", "300"))
    except ValueError:
        api_timeout = 300
        
    try:
        api_max_attempts = int(os.environ.get("API_MAX_ATTEMPTS", "4"))
    except ValueError:
        api_max_attempts = 4
        
    max_retries = max(0, api_max_attempts - 1)
    base_delay = 5.0
    
    print(f"[Ollama Request]: Calling model '{model_name}' on {api_url} (Prompt len: {len(prompt)}, Timeout: {api_timeout}s, Attempts limit: {api_max_attempts})...", flush=True)
    t_start = time.time()
    
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=api_timeout) as response:
                t_duration = time.time() - t_start
                res_data = json.loads(response.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"].strip()
                
                # Update statistics
                _token_stats["total_requests"] += 1
                _token_stats["local_requests"] += 1
                usage = res_data.get("usage", {})
                in_t = 0
                out_t = 0
                if usage:
                    in_t = usage.get("prompt_tokens", 0)
                    out_t = usage.get("completion_tokens", 0)
                    _token_stats["total_input_tokens"] += in_t
                    _token_stats["local_input_tokens"] += in_t
                    _token_stats["total_output_tokens"] += out_t
                    _token_stats["local_output_tokens"] += out_t
                print(f"[Ollama Success]: Model '{model_name}' responded in {t_duration:.2f}s (Tokens: {in_t} in, {out_t} out)", flush=True)
                return content
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
        except (socket.timeout, TimeoutError) as e:
            print(f"[API Timeout Error - Attempt {attempt+1}/{max_retries+1}]: local model generation timed out after {api_timeout}s ({e}).", flush=True)
            if attempt < max_retries:
                print(f"Sleeping for {base_delay} seconds before retrying...", flush=True)
                time.sleep(base_delay)
                continue
            raise OllamaConnectionException(f"Timeout during local generation after {api_max_attempts} attempts: {e}")
        except (urllib.error.URLError, ConnectionError) as e:
            print(f"[API URL/Connection Error - Attempt {attempt+1}/{max_retries+1}]: {e}", flush=True)
            if attempt < max_retries:
                time.sleep(1.0)
                continue
            raise OllamaConnectionException(f"Connection failure to {api_url} after {api_max_attempts} attempts: {e}")
        except Exception as e:
            print(f"[API Error]: {e}", flush=True)
            return "{}" if json_mode else f"Error: {e}"
            
    raise QuotaLimitReachedException("API Quota Exceeded. Max retries exhausted.")

def load_generic_config():
    """Dynamically parses and syncs API_KEY, MODEL_NAME, and API_URL from .env to support runtime updates."""
    global _api_configured, _api_key, _model_name, _api_url
    global _complex_api_configured, _complex_api_key, _complex_model_name, _complex_api_url
    
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
    for key in ["API_KEY", "MODEL_NAME", "API_URL", "COMPLEX_API_KEY", "COMPLEX_MODEL_NAME", "COMPLEX_API_URL"]:
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

    complex_api_key = os.environ.get("COMPLEX_API_KEY")
    complex_model_name = os.environ.get("COMPLEX_MODEL_NAME")
    complex_api_url = os.environ.get("COMPLEX_API_URL", "")

    if complex_api_key:
        _complex_api_configured = True
        _complex_api_key = complex_api_key
        _complex_model_name = complex_model_name
        _complex_api_url = complex_api_url
        if not complex_api_url:
            genai.configure(api_key=complex_api_key)
    else:
        _complex_api_configured = False
        _complex_api_key = ""
        _complex_model_name = ""
        _complex_api_url = ""

def call_llm(prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False, use_complex: bool = False) -> str:
    """
    Sends a generation request to either native Gemini SDK or OpenAI-compatible endpoint.
    Automatically configures itself based on API_KEY, MODEL_NAME, and API_URL in the environment/.env file.
    Supports use_complex routing and auto-fallback if local Ollama fails.
    """
    global _api_configured, _api_key, _model_name, _api_url
    global _complex_api_configured, _complex_api_key, _complex_model_name, _complex_api_url
    global _token_stats
    
    load_generic_config()
    
    # Decide which config to use initially
    active_api_key = _api_key
    active_model_name = _model_name
    active_api_url = _api_url
    active_configured = _api_configured
    is_complex_routed = False
    
    if use_complex:
        if _complex_api_configured and _complex_api_key:
            active_api_key = _complex_api_key
            active_model_name = _complex_model_name
            active_api_url = _complex_api_url
            active_configured = _complex_api_configured
            is_complex_routed = True
        else:
            print("[StoryAnalyst Warning]: use_complex=True but COMPLEX_API_KEY is not configured. Falling back to standard config.", flush=True)
            
    if not active_configured or not active_api_key:
        return "{}" if json_mode else "Fallback LLM output."

    try:
        # If API_URL is specified, route to the OpenAI-compatible custom endpoint (e.g. Groq, local Ollama)
        if active_api_url:
            return call_openai_compatible_api(prompt, system_instruction, json_mode, active_api_key, active_model_name, active_api_url)

        # Gemini API
        genai.configure(api_key=active_api_key)
        generation_config = {}
        if json_mode:
            generation_config["response_mime_type"] = "application/json"

        max_retries = 3
        base_delay = 12.0

        # Introduce a spacing delay (5 seconds) before each Gemini API request to prevent hitting rate limits
        time.sleep(5.0)

        for attempt in range(max_retries + 1):
            try:
                g_model_name = active_model_name or "gemini-2.5-flash"
                print(f"[Gemini Request]: Calling model '{g_model_name}' (Prompt len: {len(prompt)})...", flush=True)
                t_start = time.time()
                
                model = genai.GenerativeModel(
                    model_name=g_model_name,
                    generation_config=generation_config,
                    system_instruction=system_instruction
                )
                response = model.generate_content(prompt)
                t_duration = time.time() - t_start
                
                # Update statistics
                _token_stats["total_requests"] += 1
                _token_stats["remote_requests"] += 1
                in_t = 0
                out_t = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    in_t = response.usage_metadata.prompt_token_count
                    out_t = response.usage_metadata.candidates_token_count
                    _token_stats["total_input_tokens"] += in_t
                    _token_stats["remote_input_tokens"] += in_t
                    _token_stats["total_output_tokens"] += out_t
                    _token_stats["remote_output_tokens"] += out_t
                    
                print(f"[Gemini Success]: Model '{g_model_name}' responded in {t_duration:.2f}s (Tokens: {in_t} in, {out_t} out)", flush=True)
                return response.text.strip()
            except Exception as e:
                err_msg = str(e)
                print(f"[LLM Error - Attempt {attempt + 1}/{max_retries + 1}]: {e}", flush=True)
                
                # Catch rate limits and quota exceeded errors
                if "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
                    if attempt < max_retries:
                        # Try parsing recommended retry delay
                        sleep_time = 40.0
                        match_seconds = re.search(r"seconds:\s*(\d+)", err_msg)
                        match_retry_in = re.search(r"Please retry in\s*([\d\.]+)", err_msg)
                        if match_seconds:
                            sleep_time = float(match_seconds.group(1)) + 2.0
                        elif match_retry_in:
                            sleep_time = float(match_retry_in.group(1)) + 2.0
                            
                        print(f"Rate limit / Free Tier quota hit. Sleeping for {sleep_time:.2f} seconds before retrying...", flush=True)
                        time.sleep(sleep_time)
                        continue
                    else:
                        raise QuotaLimitReachedException("Gemini API Quota Exceeded. Max retries exhausted.")
                
                return "{}" if json_mode else f"Error call_llm: {e}"
 
        raise QuotaLimitReachedException("Gemini API Quota Exceeded. Max retries exhausted.")

    except OllamaConnectionException as e:
        # Catch local Ollama connection issues and fall back to Gemini
        fallback_api_key = _complex_api_key or os.environ.get("COMPLEX_API_KEY") or os.environ.get("GEMINI_API_KEY")
        fallback_model_name = _complex_model_name or os.environ.get("COMPLEX_MODEL_NAME") or "gemini-2.5-flash"
        
        if not fallback_api_key and _api_key and _api_key != "ollama":
            fallback_api_key = _api_key
            fallback_model_name = _model_name
            
        if fallback_api_key:
            print(f"[WARNING] Local server failed ({e}). Falling back to Gemini API.", flush=True)
            genai.configure(api_key=fallback_api_key)
            generation_config = {}
            if json_mode:
                generation_config["response_mime_type"] = "application/json"
            
            max_retries = 3
            base_delay = 12.0
            
            # Introduce a spacing delay (5 seconds) before each Gemini Fallback request to prevent hitting rate limits
            time.sleep(5.0)
            
            for attempt in range(max_retries + 1):
                try:
                    print(f"[Gemini Fallback Request]: Calling model '{fallback_model_name}' (Prompt len: {len(prompt)})...", flush=True)
                    t_start = time.time()
                    
                    model = genai.GenerativeModel(
                        model_name=fallback_model_name,
                        generation_config=generation_config,
                        system_instruction=system_instruction
                    )
                    response = model.generate_content(prompt)
                    t_duration = time.time() - t_start
                    
                    # Update statistics
                    _token_stats["total_requests"] += 1
                    _token_stats["remote_requests"] += 1
                    in_t = 0
                    out_t = 0
                    if hasattr(response, "usage_metadata") and response.usage_metadata:
                        in_t = response.usage_metadata.prompt_token_count
                        out_t = response.usage_metadata.candidates_token_count
                        _token_stats["total_input_tokens"] += in_t
                        _token_stats["remote_input_tokens"] += in_t
                        _token_stats["total_output_tokens"] += out_t
                        _token_stats["remote_output_tokens"] += out_t
                        
                    print(f"[Gemini Fallback Success]: Model '{fallback_model_name}' responded in {t_duration:.2f}s (Tokens: {in_t} in, {out_t} out)", flush=True)
                    return response.text.strip()
                except Exception as gem_err:
                    err_msg = str(gem_err)
                    print(f"[LLM Fallback Error - Attempt {attempt + 1}/{max_retries + 1}]: {gem_err}", flush=True)
                    if "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
                        if attempt < max_retries:
                            # Try parsing recommended retry delay
                            sleep_time = 40.0
                            match_seconds = re.search(r"seconds:\s*(\d+)", err_msg)
                            match_retry_in = re.search(r"Please retry in\s*([\d\.]+)", err_msg)
                            if match_seconds:
                                sleep_time = float(match_seconds.group(1)) + 2.0
                            elif match_retry_in:
                                sleep_time = float(match_retry_in.group(1)) + 2.0
                                
                            print(f"Fallback Rate limit hit. Sleeping for {sleep_time:.2f} seconds before retrying...", flush=True)
                            time.sleep(sleep_time)
                            continue
                        else:
                            raise QuotaLimitReachedException("Gemini API Quota Exceeded during fallback. Max retries exhausted.")
                    return "{}" if json_mode else f"Error fallback call_llm: {gem_err}"
        else:
            print(f"[Error] Ollama is unavailable and no remote fallback key configured: {e}", flush=True)
            return "{}" if json_mode else f"Ollama Connection Error: {e}"
