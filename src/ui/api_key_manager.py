import os
import json
from PyQt5.QtWidgets import QMessageBox, QDialog
from ui.api_key_dialog import ApiKeyDialog


class ApiKeyManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def set_api_key(self):
        dialog = ApiKeyDialog(self.main_window, current_key=self.main_window.api_key or "")
        if dialog.exec_() == QDialog.Accepted:
            new_key = dialog.get_api_key()
            if new_key:
                self.main_window.api_key = new_key
                if self._save_api_key(new_key):
                    self.main_window.statusBar().showMessage("API key saved successfully.")
            else:
                self.main_window.api_key = None
                if self._save_api_key(None):
                     self.main_window.statusBar().showMessage("API key cleared.")

    def _save_api_key(self, key_to_save):
        try:
            config_path = "settings/config.json"
            config = {}
            
            # Create template if it doesn't exist
            if not os.path.exists(config_path):
                self._create_template_config(config_path)
                
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: config.json is corrupted. Overwriting.")
                    config = {}

            if key_to_save:
                config["openrouter_api_key"] = key_to_save
            elif "openrouter_api_key" in config:
                del config["openrouter_api_key"]

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to save API key:\n{e}")
            return False

    def load_api_key(self):
        config_path = "settings/config.json"
        self.main_window.api_key = None
        
        # Create template if it doesn't exist
        if not os.path.exists(config_path):
            self._create_template_config(config_path)
            
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.main_window.api_key = config.get("openrouter_api_key")
                    if self.main_window.api_key:
                        print("API Key loaded from config.")
                    else:
                        print("API Key not found in config.")
            except json.JSONDecodeError:
                QMessageBox.warning(self.main_window, "Config Error", f"Could not read '{config_path}'. It might be corrupted.")
            except Exception as e:
                QMessageBox.warning(self.main_window, "Error", f"Failed to load API key:\n{e}")
        else:
            print(f"Config file '{config_path}' not found. No API key loaded.")

    def _create_template_config(self, config_path: str) -> None:
        """Create a template config.json file with default configuration"""
        # Ensure settings directory exists
        settings_dir = os.path.dirname(config_path)
        if settings_dir and not os.path.exists(settings_dir):
            os.makedirs(settings_dir)
            
        template_config = {
            "__comment": "do not change openrouter_api_key text",
            "default_model": "meta-llama/llama-4-maverick",
            "default_prompts": {
                "pre_system_prompt": "You are a translation assistant. Translate the final user message into **{target_language}**.",
                "post_system_prompt": "You are a translation assistant. IMPORTANT: Respond with *only* the translation of the final user message into **{target_language}**, nothing else.",
                "user_prompt": "{source_text}"
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(template_config, f, indent=4)
        print(f"Created template configuration at {config_path}")