import requests
import json
import tiktoken
from typing import Generator

# Tokenizer for consistent token counting with OpenRouter
try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    print(f"Warning: Failed to initialize tokenizer: {e}")
    tokenizer = None

def count_tokens(text: str) -> int:
    """Counts approximate tokens matching OpenRouter's counting method."""
    if tokenizer:
        return len(tokenizer.encode(text))
    return len(text) // 4  # Fallback approximation

def get_ollama_stream(endpoint: str, model: str, messages: list, parameters: dict) -> Generator[str, None, None]:
    """
    Gets streaming response from Ollama's API.
    
    Args:
        endpoint: Ollama server endpoint (e.g., "http://localhost:11434")
        model: The model name to use
        messages: Chat messages in OpenAI format
        parameters: Model parameters from models.json
    
    Yields:
        str: Response chunks as they arrive
    
    Raises:
        requests.exceptions.RequestException: On network errors
        ValueError: For invalid requests
    """
    url = f"{endpoint}/api/chat"
    headers = {"Content-Type": "application/json"}
    
    # Convert OpenAI-style messages to Ollama format
    ollama_messages = []
    for msg in messages:
        ollama_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Prepare payload with model parameters
    payload = {
        "model": model,
        "messages": ollama_messages,
        "stream": True,
        "options": {
            "temperature": parameters.get("temperature", 0.7),
            "top_p": parameters.get("top_p", 0.9),
            "top_k": parameters.get("top_k", 40),
            "num_ctx": parameters.get("max_tokens", 2048)
        }
    }

    try:
        with requests.post(url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if chunk.get("message") and chunk["message"].get("content"):
                            yield chunk["message"]["content"]
                        elif chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

    except requests.exceptions.RequestException as e:
        raise
    except Exception as e:
        raise
