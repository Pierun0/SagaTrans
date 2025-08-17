import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

class ModelManager:
    def __init__(self, config_path: str = "settings/models.json"):
        self.config_path = config_path
        self.providers: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """Load and validate the models configuration file"""
        # Create template if it doesn't exist
        if not os.path.exists(self.config_path):
            self._create_template_config()
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self._validate_config(config)
                self.providers = config.get("providers", {})
        except FileNotFoundError:
            raise FileNotFoundError(f"Models configuration file not found at {self.config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in models configuration: {e}")

    def _create_template_config(self) -> None:
        """Create a template models.json file with default configuration"""
        # Ensure settings directory exists
        settings_dir = os.path.dirname(self.config_path)
        if settings_dir and not os.path.exists(settings_dir):
            os.makedirs(settings_dir)
            
        template_config = {
            "providers": {
                "openrouter": {
                    "endpoint": "https://openrouter.ai/api/v1",
                    "api_key": "YOUR_OPENROUTER_API_KEY_HERE",
                    "models": {
                        "meta-llama/llama-4-maverick": {
                            "parameters": {
                                "seed": -1,
                                "temperature": 0.8,
                                "top_p": 0.8,
                                "top_k": 30,
                                "max_tokens": 200000
                            },
                            "options": {
                                "thinking": False
                            }
                        }
                    }
                },
                "ollama": {
                    "endpoint": "http://localhost:11434",
                    "models": {
                        "gemma3:4b": {
                            "parameters": {
                                "seed": -1,
                                "temperature": 0.7,
                                "top_p": 0.9,
                                "top_k": 40,
                                "max_tokens": 8192
                            },
                            "options": {
                                "thinking": False
                            }
                        }
                    }
                }
            }
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(template_config, f, indent=2)
        print(f"Created template models configuration at {self.config_path}")

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate the structure of the configuration"""
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a JSON object")
        if "providers" not in config:
            raise ValueError("Configuration must contain 'providers' key")
        
        for provider_name, provider_data in config["providers"].items():
            if "endpoint" not in provider_data:
                raise ValueError(f"Provider {provider_name} missing required 'endpoint'")
            if "models" not in provider_data:
                raise ValueError(f"Provider {provider_name} missing required 'models'")
            
            for model_name, model_data in provider_data["models"].items():
                if "parameters" not in model_data:
                    raise ValueError(f"Model {model_name} missing required 'parameters'")
                if "options" not in model_data:
                    raise ValueError(f"Model {model_name} missing required 'options'")

    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific provider"""
        return self.providers.get(provider_name)

    def get_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a model by full ID (provider/model)"""
        provider_name = self.get_model_provider(model_id)
        if not provider_name:
            return None

        # Correctly extract model name (everything after the first '/')
        model_name_parts = model_id.split('/', 1)
        if len(model_name_parts) > 1:
            model_name = model_name_parts[1]
        else:
            # Handle case where no provider prefix was given (shouldn't happen with current logic, but safe)
            model_name = model_id

        provider = self.get_provider_config(provider_name)
        if not provider:
            return None

        model_config = provider.get("models", {}).get(model_name) # Now searches for the correct key
        if not model_config:
            return None
            
        # Include provider-specific configuration (like API key for OpenRouter)
        provider_config = {k: v for k, v in provider.items() if k not in ["models"]}
        return {
            "endpoint": provider.get("endpoint"),
            **provider_config,
            **model_config
        }

    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all available models across all providers"""
        all_models = {}
        for provider_name, provider_data in self.providers.items():
            for model_name, model_data in provider_data.get("models", {}).items():
                # Include provider-specific configuration (like API key for OpenRouter)
                provider_config = {k: v for k, v in provider_data.items() if k not in ["models"]}
                all_models[f"{provider_name}/{model_name}"] = {
                    "provider": provider_name,
                    "model": model_name,
                    "endpoint": provider_data.get("endpoint", ""),
                    **provider_config,
                    **model_data
                }
        return all_models

    def get_model_provider(self, model_id: str) -> Optional[str]:
        """Get the provider name for a given model ID (provider/model or just model)"""
        if '/' in model_id:
            return model_id.split('/')[0]
        
        # Search through all providers if no provider specified
        for provider_name, provider_data in self.providers.items():
            if model_id in provider_data.get("models", {}):
                return provider_name
        return None


    def update_model_parameter(self, provider_name: str, model_name: str,
                             parameter: str, value: Any) -> bool:
        """Update a model parameter and save the configuration"""
        model_config = self.get_model_config(provider_name, model_name)
        if not model_config:
            return False
        
        if parameter in model_config["parameters"]:
            model_config["parameters"][parameter] = value
        elif parameter in model_config["options"]:
            model_config["options"][parameter] = value
        else:
            return False
        
        self._save_config()
        return True

    def _save_config(self) -> None:
        """Save the current configuration back to file"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump({"providers": self.providers}, f, indent=2)

    def reload_models(self):
        """Reload models from config file and return (success, message)"""
        try:
            previous_count = len(self.providers)
            self.load_config()
            new_count = len(self.providers)
            return (True, f"Reloaded models ({previous_count} -> {new_count} providers)")
        except Exception as e:
            return (False, f"Failed to reload models: {str(e)}")
