import requests
import json
from typing import Generator, Dict, Any
from model_request_handler import ModelRequestHandler

class OpenRouterAdapter(ModelRequestHandler):
    def __init__(self, model_id: str, config: Dict[str, Any]):
        self.model_id = model_id
        self.config = config
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.api_key = config.get("api_key")  # Get API key from config
        if not self._validate_model_id():
            raise ValueError(f"Invalid OpenRouter model ID format: {model_id}")

    def _validate_model_id(self) -> bool:
        """Validate the OpenRouter model ID format"""
        parts = self.model_id.split('/')
        return len(parts) >= 2 and all(parts)  # At least provider/model


    def validate_connection(self) -> bool:
        if not self.api_key:
            return False
            
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/Pierun0/SagaTrans",
                "X-Title": "SagaTrans"
            }
            response = requests.get("https://openrouter.ai/api/v1/auth/key", 
                                 headers=headers, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def send_request(self, payload: Dict[str, Any]) -> Generator[str, None, None]:
        if not self.api_key:
            raise Exception("API key not set for OpenRouter")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/Pierun0/SagaTrans",
            "X-Title": "SagaTrans",
            "Content-Type": "application/json"
        }

        # Convert parameters to OpenRouter format
        converted_params = self._convert_parameters(self.config.get('parameters', {}))
        # Use full model name after provider prefix (e.g. "meta-llama/llama-4-maverick:free")
        model_name = '/'.join(self.model_id.split('/')[1:])
        openrouter_payload = {
            "model": model_name,
            "messages": payload["messages"],
            "stream": True,
            **converted_params
        }
        try:
            with requests.post(self.endpoint, json=openrouter_payload,
                             headers=headers, stream=True, timeout=60*10) as response:
                # Check for specific status codes
                if response.status_code == 403:
                    # Try to get detailed error message from response
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "Access denied")
                    except (json.JSONDecodeError, ValueError):
                        error_msg = response.text or "Access denied"
                    
                    # Differentiate between different types of 403 errors
                    if "api key" in error_msg.lower() or "invalid api key" in error_msg.lower():
                        raise Exception(f"OpenRouter API key error: {error_msg}")
                    elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        raise Exception(f"OpenRouter quota exceeded: {error_msg}")
                    elif "model" in error_msg.lower() and "access" in error_msg.lower():
                        raise Exception(f"OpenRouter model access denied: {error_msg}")
                    else:
                        raise Exception(f"OpenRouter access denied (403): {error_msg}")
                
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
                            except json.JSONDecodeError as e:
                                continue
        except requests.exceptions.RequestException as e:
            # Check if this is a 403 error that wasn't caught above
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 403:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", "Access denied")
                except (json.JSONDecodeError, ValueError):
                    error_msg = e.response.text or "Access denied"
                
                if "api key" in error_msg.lower() or "invalid api key" in error_msg.lower():
                    raise Exception(f"OpenRouter API key error: {error_msg}")
                elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                    raise Exception(f"OpenRouter quota exceeded: {error_msg}")
                elif "model" in error_msg.lower() and "access" in error_msg.lower():
                    raise Exception(f"OpenRouter model access denied: {error_msg}")
                else:
                    raise Exception(f"OpenRouter access denied (403): {error_msg}")
            else:
                raise Exception(f"OpenRouter request failed: {str(e)}")

    def get_parameters(self) -> Dict[str, Any]:
        return self.config.get('parameters', {})

    def convert_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._convert_parameters(params)

    def _convert_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standardized parameters to OpenRouter-specific format"""
        return {
            "temperature": params.get("temperature", 0.7),
            "top_p": params.get("top_p", 0.9),
            "top_k": params.get("top_k", 40),
            "max_tokens": params.get("max_tokens_completion", 16000),  # Cap 16000 tokens completion if not specified
            "include_reasoning": params.get("thinking", False)
            #"include_reasoning": params.get("thinking_included", 'false')
        }
