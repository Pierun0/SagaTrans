import json
import os
from PyQt5.QtWidgets import QMessageBox # Import QMessageBox

CONFIG_FILE = "settings/config.json"
PROJECTS_INDEX_FILE = "projects.json"
PROJECTS_DIR = "projects"

# --- Helper Function for Filename ---
def sanitize_filename(name):
    """Creates a safe filename from a project title."""
    # Remove invalid characters, replace spaces with underscores
    name = "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()
    return name.replace(' ', '_') + ".json"

def load_api_key():
    """Loads only the API key from config file."""
    # Create template if it doesn't exist
    if not os.path.exists(CONFIG_FILE):
        _create_template_config()
        
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        api_key = config.get("openrouter_api_key")

        if not api_key or api_key == "YOUR_OPENROUTER_API_KEY_HERE":
             QMessageBox.critical(None, "Config Error", f"OpenRouter API Key not found or invalid in {CONFIG_FILE}. Please add it and restart.")
             return None
        return api_key
    except FileNotFoundError:
        QMessageBox.critical(None, "Config Error", f"{CONFIG_FILE} not found.")
        return None
    except json.JSONDecodeError:
        QMessageBox.critical(None, "Config Error", f"Error decoding {CONFIG_FILE}.")
        return None
    except Exception as e:
         QMessageBox.critical(None, "Config Error", f"An unexpected error occurred loading config: {e}")
         return None

def load_projects_index():
    """Loads the project index file."""
    try:
        with open(PROJECTS_INDEX_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Create the file if it doesn't exist
        try:
            with open(PROJECTS_INDEX_FILE, 'w') as f:
                json.dump({}, f)
            return {}
        except IOError as e:
             QMessageBox.critical(None, "Error", f"Failed to create projects index file: {e}")
             return {} # Return empty dict on error
    except json.JSONDecodeError:
        QMessageBox.critical(None, "Error", f"Error decoding {PROJECTS_INDEX_FILE}. Starting with empty index.")
        return {} # Return empty dict on error
    except Exception as e:
        QMessageBox.critical(None, "Error", f"An unexpected error occurred loading project index: {e}")
        return {}

def save_projects_index(projects_index):
    """Saves the project index file."""
    try:
        with open(PROJECTS_INDEX_FILE, 'w') as f:
            json.dump(projects_index, f, indent=4)
        return True
    except IOError as e:
        QMessageBox.critical(None, "Error", f"Failed to save projects index: {e}")
        return False
    except Exception as e:
        QMessageBox.critical(None, "Error", f"An unexpected error occurred saving project index: {e}")
        return False

def load_project_file(project_filename):
    """Loads a specific project's data from its JSON file."""
    filepath = os.path.join(PROJECTS_DIR, project_filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
        return project_data
    except FileNotFoundError:
        QMessageBox.critical(None, "Error", f"Project file not found: {filepath}")
        return None
    except json.JSONDecodeError:
        QMessageBox.critical(None, "Error", f"Error decoding project file: {filepath}")
        return None
    except Exception as e:
        QMessageBox.critical(None, "Error", f"An unexpected error occurred loading project file: {e}")
        return None

def save_project_file(project_filename, project_data):
    """Saves a specific project's data to its JSON file."""
    if not project_data or not project_filename:
        QMessageBox.warning(None, "Save Project", "Invalid data or filename provided for saving.")
        return False
    filepath = os.path.join(PROJECTS_DIR, project_filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=4, ensure_ascii=False)
            return True
    except IOError as e:
        QMessageBox.critical(None, "Error", f"Failed to save project file '{filepath}': {e}")
        return False
    except Exception as e:
        QMessageBox.critical(None, "Error", f"An unexpected error occurred saving project: {e}")
        return False

def create_project_file(filepath, project_data):
    """Creates and saves a new project file."""
    try:
        # Ensure the projects directory exists
        if not os.path.exists(PROJECTS_DIR):
            os.makedirs(PROJECTS_DIR)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        QMessageBox.critical(None, "Error", f"Failed to create project file '{os.path.basename(filepath)}': {e}")
        return False
    except Exception as e:
        QMessageBox.critical(None, "Error", f"An unexpected error occurred creating project file: {e}")
        return False

def delete_project_file(project_filename):
    """Deletes a project file."""
    filepath = os.path.join(PROJECTS_DIR, project_filename)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        else:
            return False # Indicate file wasn't found, though index might be updated
    except OSError as e:
        QMessageBox.critical(None, "Error", f"Failed to delete project file '{project_filename}': {e}")
        return False
    except Exception as e:
        QMessageBox.critical(None, "Error", f"An unexpected error occurred deleting project file: {e}")
        return False

def load_config_defaults():
    """Loads default prompts from config.json."""
    config_path = CONFIG_FILE
    defaults = {}
    
    # Create template if it doesn't exist
    if not os.path.exists(config_path):
        _create_template_config()
        
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                defaults = config.get("default_prompts", {})
        except json.JSONDecodeError:
            print(f"Warning: config.json is corrupted. Using empty defaults.")
        except Exception as e:
            print(f"Warning: Failed to load config defaults: {e}")
    else:
        print(f"Warning: config.json not found. Using empty defaults.")
    return defaults

def _create_template_config() -> None:
    """Create a template config.json file with default configuration"""
    # Ensure settings directory exists
    settings_dir = os.path.dirname(CONFIG_FILE)
    if settings_dir and not os.path.exists(settings_dir):
        os.makedirs(settings_dir)
        
    template_config = {
        "__comment": "do not change openrouter_api_key text",
        "openrouter_api_key": "YOUR_OPENROUTER_API_KEY_HERE",
        "default_model": "google/gemma-3-27b-it:free",
        "undo_max_steps": 50,
        "undo_interval_seconds": 20,
        "default_prompts": {
            "pre_system_prompt": "You are a translation assistant. Translate the final user message into **{target_language}**.",
            "post_system_prompt": "You are a translation assistant. IMPORTANT: Respond with *only* the translation of the final user message into **{target_language}**, nothing else.",
            "user_prompt": "{source_text}"
        }
    }
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(template_config, f, indent=4)
    print(f"Created template configuration at {CONFIG_FILE}")
