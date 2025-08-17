from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                            QDialogButtonBox, QLabel, QMessageBox, QComboBox)
from data_manager import load_config_defaults # Import the centralized function

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")

        self.default_prompts = load_config_defaults() # Load defaults from config

        layout = QVBoxLayout()
        form = QFormLayout()

        # Basic project info
        self.title_edit = QLineEdit()
        self.desc_edit = QLineEdit()
        self.author_edit = QLineEdit()
        self.lang_edit = QLineEdit()
        self.model_edit = QLineEdit()
        self.model_edit.setText("google/gemini-2.0-flash-exp:free") # Set default model
        self.limit_edit = QLineEdit()
        self.limit_edit.setPlaceholderText("Optional, e.g., 8000, leave empty for default")

        # Prompt configuration
        self.system_prompt_edit = QLineEdit()
        self.system_prompt_edit.setPlaceholderText(
            "You are a translation assistant. Translate to {target_language}..."
        )
        self.system_prompt_end_edit = QLineEdit()
        self.system_prompt_end_edit.setPlaceholderText(
            "IMPORTANT: Respond with *only* the translation into {target_language}, nothing else."
        )
        self.user_prompt_edit = QLineEdit()
        self.user_prompt_edit.setPlaceholderText(
            "{source_text}"
        )

        form.addRow("Title:", self.title_edit)
        form.addRow("Description:", self.desc_edit)
        form.addRow("Author:", self.author_edit)
        form.addRow("Target Language:", self.lang_edit)
        form.addRow("Model:", self.model_edit)
        form.addRow("Context Token Limit:", self.limit_edit)
        form.addRow(QLabel("<b>Prompt Configuration</b>"))
        form.addRow("System Prompt Start:", self.system_prompt_edit)
        form.addRow("System Prompt End:", self.system_prompt_end_edit)
        form.addRow("User Content:", self.user_prompt_edit)

        # Context selection mode
        form.addRow(QLabel("<b>Context Selection</b>"))
        self.context_mode_combo = QComboBox()
        modes = [
            ("Automatic (Fill Budget)", "fill_budget"),
            ("Automatic (Strict Nearby)", "nearby"), 
            ("Manual (Checkboxes)", "manual")
        ]
        for text, _ in modes:
            self.context_mode_combo.addItem(text)
        self.context_mode_combo.setCurrentText("Automatic (Fill Budget)")
        form.addRow("Context Mode:", self.context_mode_combo)

        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def validate_and_accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Input Error", "Project title cannot be empty.")
            return

        # Validate token limit input
        limit_text = self.limit_edit.text().strip()
        if limit_text:
            try:
                int(limit_text)
            except ValueError:
                QMessageBox.warning(self, "Input Error", "Context Token Limit must be a valid number or empty.")
                return

        self.accept()

    def get_project_details(self):
        limit_text = self.limit_edit.text().strip()
        limit_value = -1 # Default if empty or invalid
        if limit_text:
            try:
                limit_value = int(limit_text)
            except ValueError:
                # Should be caught by validate_and_accept, but handle defensively
                print(f"Warning: Invalid integer value '{limit_text}' for token limit, using -1.")
                limit_value = -1

        # Include prompt_config keys only if the text differs from the default
        prompt_config = {}
        if self.system_prompt_edit.text().strip() != self.default_prompts.get("pre_system_prompt", ""):
            prompt_config["system_prompt"] = self.system_prompt_edit.text().strip()
        if self.system_prompt_end_edit.text().strip() != self.default_prompts.get("post_system_prompt", ""):
            prompt_config["post_system_prompt"] = self.system_prompt_end_edit.text().strip()
        if self.user_prompt_edit.text().strip() != self.default_prompts.get("user_prompt", ""):
            prompt_config["user_prompt_template"] = self.user_prompt_edit.text().strip()

        return {
            "title": self.title_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "author": self.author_edit.text().strip(),
            "target_language": self.lang_edit.text().strip(),
            "model": self.model_edit.text().strip() or "google/gemini-2.0-flash-exp:free", # Ensure default if cleared
            "context_token_limit_approx": limit_value,
            "context_selection_mode": {
                "Manual (Checkboxes)": "manual",
                "Automatic (Strict Nearby)": "nearby",
                "Automatic (Fill Budget)": "fill_budget"
            }.get(self.context_mode_combo.currentText(), "fill_budget"),
            **({"prompt_config": prompt_config} if prompt_config else {})
        }
