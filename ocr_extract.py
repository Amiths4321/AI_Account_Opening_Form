"""
Extracts structured fields from Indian ID documents (Aadhaar / PAN / Driving License)
using a self-hosted Qwen2.5-VL model served locally through Ollama.

Requires Ollama running on the remote server with the model pulled, e.g.:
    ollama pull qwen2.5vl:7b
    OLLAMA_HOST=0.0.0.0 ollama serve
"""
import base64
import json
import re
import requests

PROMPTS = {
    "Aadhaar": (
        "This is an image of an Indian Aadhaar card. Look carefully and extract the following "
        "fields. Respond with ONLY a JSON object (no markdown, no explanation) with exactly these "
        "keys: full_name, dob, gender, aadhaar_number, address. "
        "dob must be in DD/MM/YYYY format. aadhaar_number must be the 12 digits with no spaces. "
        "If a field is not clearly visible, set its value to null."
    ),
    "PAN": (
        "This is an image of an Indian PAN card. Look carefully and extract the following fields. "
        "Respond with ONLY a JSON object (no markdown, no explanation) with exactly these keys: "
        "full_name, father_name, dob, pan_number. "
        "dob must be in DD/MM/YYYY format. pan_number is the 10-character alphanumeric code. "
        "If a field is not clearly visible, set its value to null."
    ),
    "Driving License": (
        "This is an image of an Indian Driving License. Look carefully and extract the following "
        "fields. Respond with ONLY a JSON object (no markdown, no explanation) with exactly these "
        "keys: full_name, dob, dl_number, address, validity_date. "
        "dob and validity_date must be in DD/MM/YYYY format. "
        "If a field is not clearly visible, set its value to null."
    ),
}


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def mask_aadhaar(number):
    """UIDAI guidance: never display/store the full Aadhaar number — only the last 4 digits."""
    if not number:
        return number
    digits = re.sub(r"\D", "", str(number))
    if len(digits) < 4:
        return "XXXX XXXX XXXX"
    return f"XXXX XXXX {digits[-4:]}"


def _strip_to_json(raw_text):
    """Models sometimes wrap JSON in ```json fences even when told not to — strip those off."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def call_ollama(image_path, doc_type, ollama_host, model, timeout_seconds):
    """
    Sends the document image + an extraction prompt to a self-hosted Qwen2.5-VL model via Ollama.
    Returns (success: bool, data_or_none: dict, raw_response_text: str, error_message: str)
    """
    prompt = PROMPTS.get(doc_type)
    if prompt is None:
        return False, None, "", f"Unsupported document type: {doc_type}"

    try:
        image_b64 = encode_image(image_path)
    except Exception as e:
        return False, None, "", f"Could not read uploaded image: {e}"

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt, "images": [image_b64]}
        ],
        "format": "json",
        "stream": False,
    }

    try:
        resp = requests.post(f"{ollama_host}/api/chat", json=payload, timeout=timeout_seconds)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        return False, None, "", (
            "Could not reach the Ollama server. Make sure 'ollama serve' is running "
            f"and reachable at {ollama_host}."
        )
    except requests.exceptions.Timeout:
        return False, None, "", "Ollama took too long to respond (timed out)."
    except requests.exceptions.HTTPError as e:
        return False, None, "", f"Ollama returned an error: {e}"
    except Exception as e:
        return False, None, "", f"Unexpected error calling Ollama: {e}"

    try:
        raw_text = resp.json()["message"]["content"]
    except (KeyError, ValueError) as e:
        return False, None, "", f"Unexpected response shape from Ollama: {e}"

    cleaned = _strip_to_json(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return False, None, raw_text, "The model's response wasn't valid JSON — try re-uploading a clearer image."

    if doc_type == "Aadhaar" and data.get("aadhaar_number"):
        data["aadhaar_number"] = mask_aadhaar(data["aadhaar_number"])

    return True, data, raw_text, ""


def extract_document(image_path, doc_type, ollama_host, model, timeout_seconds):
    return call_ollama(image_path, doc_type, ollama_host, model, timeout_seconds)