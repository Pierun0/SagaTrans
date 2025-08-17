import requests
import json
import os
import time
import tiktoken

# --- Constants ---
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- Tokenizer Initialization ---
try:
    # Using cl100k_base encoding as a general approximation
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    print(f"Warning: Failed to initialize tokenizer: {e}")
    tokenizer = None

def count_tokens(text: str) -> int:
    """Counts approximate tokens using the initialized tokenizer."""
    if tokenizer:
        return len(tokenizer.encode(text))
    else:
        # Fallback: rough estimate (e.g., chars / 4) if tokenizer failed
        return len(text) // 4

def get_translation_stream(api_key: str, payload: dict):
    """
    Gets translation from OpenRouter using the Chat Completions endpoint as a stream,
    using a pre-constructed payload.

    Args:
        api_key: The OpenRouter API key.
        payload: The dictionary containing the full request payload (model, messages, stream).

    Yields:
        str: Chunks of the translated text as they arrive.

    Raises:
        requests.exceptions.RequestException: If a network error occurs.
        Exception: For other potential errors during streaming/parsing.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        'HTTP-Referer': 'https://github.com/Pierun0/SagaTrans',
        'X-Title': 'SagaTrans',
        "Content-Type": "application/json"
    }

    # Ensure payload is valid
    if not payload or "model" not in payload or "messages" not in payload:
        raise ValueError("Invalid payload provided to get_translation_stream.")

    model_name = payload.get("model", "Unknown Model")
    # Extract target language from system prompt if possible for logging (best effort)
    target_language = "Unknown"
    try:
        system_content = payload["messages"][0]["content"]
        lang_marker = "into **"
        start_idx = system_content.find(lang_marker)
        if start_idx != -1:
            end_idx = system_content.find("**", start_idx + len(lang_marker))
            if end_idx != -1:
                target_language = system_content[start_idx + len(lang_marker):end_idx]
    except Exception:
        pass # Ignore errors in extracting language for logging

    # Use the provided payload directly
    data = payload
    
    try:
        with requests.post(API_URL, headers=headers, json=data, stream=True, timeout=90) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        json_str = decoded_line[len('data: '):]
                        if json_str.strip() == '[DONE]':
                            break
                        try:
                            chunk = json.loads(json_str)
                            if chunk.get("choices"):
                                delta = chunk["choices"][0].get("delta")
                                if delta and "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
    except requests.exceptions.RequestException as e:
        raise
    except Exception as e:
        raise
