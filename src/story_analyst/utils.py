import uuid
import google.generativeai as genai
import os
import re
import json
from typing import Optional, Any

_api_configured = False

def configure_api(api_key: str):
    """Configures the google.generativeai API key globally."""
    global _api_configured
    genai.configure(api_key=api_key)
    _api_configured = True

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

def call_llm(prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False) -> str:
    """
    Sends a generation request to the gemini-2.5-flash model.
    Supports JSON output constraints via json_mode.
    """
    global _api_configured
    if not _api_configured:
        env_key = os.environ.get("GEMINI_API_KEY")
        if env_key:
            configure_api(env_key)
        else:
            # Try finding in .env file in parent directories
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
                                    if k.strip() == "GEMINI_API_KEY":
                                        configure_api(v.strip().strip("'\""))
                                        break
                    except Exception:
                        pass
                    if _api_configured:
                        break
                parent = os.path.dirname(current_dir)
                if parent == current_dir:
                    break
                current_dir = parent

    if not _api_configured:
        return "{}" if json_mode else "Fallback LLM output."

    generation_config = {}
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config,
            system_instruction=system_instruction
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[LLM Error]: {e}", flush=True)
        return "{}" if json_mode else f"Error call_llm: {e}"
