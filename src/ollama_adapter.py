import requests
import json
from typing import Generator, Dict, Any
from model_request_handler import ModelRequestHandler

class OllamaAdapter(ModelRequestHandler):
    def __init__(self, model_id: str, config: Dict[str, Any]):
        self.model_id = model_id  # Keep full ID for API requests
        self.config = config
        self.endpoint = config['endpoint']  # Required - no default
        if not self.endpoint.startswith(('http://', 'https://')):
            self.endpoint = f'http://{self.endpoint}'
        # Remove only the first segment (provider prefix) for validation
        self.model_name = '/'.join(model_id.split('/')[1:])  # Gets "hf.co/unsloth/..."

    def validate_connection(self) -> bool:
        try:
            response = requests.get(
                f"{self.endpoint}/api/tags",
                timeout=(3.05, 600)  # Connect timeout 3.05s, read timeout 600s (10 min)
            )
            if response.status_code == 200:
                models = response.json().get('models', [])
                # Check model_name (without provider prefix) since server doesn't include it
                if not any(m['name'] == self.model_name for m in models):
                    return False
                return True
            return False
        except requests.exceptions.RequestException as e:
            return False

    def send_request(self, payload: Dict[str, Any]) -> Generator[str, None, None]:
        url = f"{self.endpoint}/api/chat"
        headers = {"Content-Type": "application/json"}
        
        # Convert messages to Ollama format
        messages = []
        for msg in payload['messages']:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Prepare payload with model parameters using the base model name
        options = self._convert_parameters(self.config.get('parameters', {}))
        
        ollama_payload = {
            "model": self.model_name,  # Use base model name known by Ollama server
            "messages": messages,
            "stream": True,
            "options": options
        }

        try:
            with requests.post(
                url, 
                json=ollama_payload, 
                headers=headers, 
                stream=True,
                timeout=(3.05, 600)  # Connect timeout 3.05s, read timeout 600s (10 min)
            ) as response:
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
        except requests.exceptions.Timeout:
            raise Exception("Ollama request timed out - server not responding")
        except requests.exceptions.ConnectionError:
            raise Exception("Could not connect to Ollama server - check if it's running")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Model not found: {self.model_id}")
            raise Exception(f"Ollama API error: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama request failed: {str(e)}")

    def get_parameters(self) -> Dict[str, Any]:
        return self.config.get('parameters', {})

    def convert_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._convert_parameters(params)

    def _convert_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standardized parameters to Ollama-specific format"""
        options = {
            "temperature": params.get("temperature", 0.7),
            "top_p": params.get("top_p", 0.9),
            "top_k": params.get("top_k", 40),
            "num_ctx": params.get("max_tokens", 16000),
            "use_mmap": params.get("use_mmap", True),
            "use_mlock": params.get("use_mlock", False)
        }
        
        # Special handling for seed - only include if >= 0
        seed = params.get("seed", -1)
        if seed >= 0:
            options["seed"] = seed
        
        # Add thinking mode if specified in config
        if 'options' in self.config and 'thinking' in self.config['options']:
            options['enable_thinking'] = self.config['options']['thinking']
            
        return options
