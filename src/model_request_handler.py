from abc import ABC, abstractmethod
from typing import Generator, Dict, Any, Optional

class ModelRequestHandler(ABC):
    """Abstract base class for model request handlers"""
    
    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate connection to the model provider"""
        pass
        
    @abstractmethod
    def send_request(self, payload: Dict[str, Any]) -> Generator[str, None, None]:
        """Send request to model and yield response chunks"""
        pass
        
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get model parameters in standardized format"""
        pass
        
    @abstractmethod
    def convert_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standardized parameters to provider-specific format"""
        pass
        
    @staticmethod
    def create_handler(model_id: str, config: Dict[str, Any]) -> Optional['ModelRequestHandler']:
        """Factory method to create appropriate handler based on model ID"""
        if not model_id or not config:
            return None
            
        # Handle both prefixed and non-prefixed model names
        model_parts = model_id.split('/')
        if len(model_parts) > 1:
            provider = model_parts[0]
            model_name = '/'.join(model_parts[1:])  # Handle nested model names
        else:
            provider = 'ollama'  # Default provider
            model_name = model_id
            
        try:
            if provider == 'ollama':
                from ollama_adapter import OllamaAdapter
                return OllamaAdapter(model_id, config)  # Pass full model_id to preserve prefix
            elif provider == 'openrouter':
                from openrouter_adapter import OpenRouterAdapter
                return OpenRouterAdapter(model_id, config)  # Pass full model_id
                
            return None
        except Exception as e:
            return None
