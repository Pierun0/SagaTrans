from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QLabel, QComboBox, QTextEdit, QPushButton,
    QMessageBox
)
from data_manager import load_config_defaults # Import the centralized function

class ProjectSettingsDialog(QDialog):
    def __init__(self, parent=None, data=None, model_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.model_manager = model_manager

        self.data = data or {}
        self.default_prompts = load_config_defaults() # Load defaults using the centralized function

        layout = QVBoxLayout()
        form = QFormLayout()

        # Basic project info
        self.title_edit = QLineEdit(self.data.get("title", ""))
        self.desc_edit = QLineEdit(self.data.get("description", ""))
        self.lang_edit = QLineEdit(self.data.get("target_language", ""))
        self.author_edit = QLineEdit(self.data.get("author", ""))
        # Model selection combo box
        self.model_combo = QComboBox()
        if self.model_manager:
            models = self.model_manager.get_all_models()
            for model_name in models:
                self.model_combo.addItem(model_name)
            current_model = self.data.get("model", "")
            if current_model in models:
                self.model_combo.setCurrentText(current_model)
        else:
            self.model_combo.addItem(self.data.get("model"))
        self.limit_edit = QLineEdit(str(self.data.get("context_token_limit_approx", -1)))

        # Prompt configuration - Prioritize project data, then config defaults, then empty
        prompt_config = self.data.get("prompt_config", {})

        self.pre_system_prompt_edit = QTextEdit()
        pre_system_default = self.default_prompts.get("pre_system_prompt", "")
        # Use project prompt only if it exists and is not empty, otherwise use default
        pre_system_text = prompt_config.get("pre_system_prompt")
        self.pre_system_prompt_edit.setPlainText(pre_system_text if pre_system_text else pre_system_default)
        self.pre_system_prompt_edit.setPlaceholderText(
            f"Default: {pre_system_default}" if pre_system_default else "Enter pre-context system prompt..."
        )

        self.post_system_prompt_edit = QTextEdit()
        post_system_default = self.default_prompts.get("post_system_prompt", "")
        # Use project prompt only if it exists and is not empty, otherwise use default
        post_system_text = prompt_config.get("post_system_prompt")
        self.post_system_prompt_edit.setPlainText(post_system_text if post_system_text else post_system_default)
        self.post_system_prompt_edit.setPlaceholderText(
            f"Default: {post_system_default}" if post_system_default else "Enter post-context system prompt..."
        )

        self.user_prompt_edit = QTextEdit()
        user_prompt_default = self.default_prompts.get("user_prompt", "")
        # Use project prompt only if it exists and is not empty, otherwise use default
        user_prompt_text = prompt_config.get("user_prompt")
        self.user_prompt_edit.setPlainText(user_prompt_text if user_prompt_text else user_prompt_default)
        self.user_prompt_edit.setPlaceholderText(
            f"Default: {user_prompt_default}" if user_prompt_default else "Enter user prompt template..."
        )

        form.addRow("Title:", self.title_edit)
        form.addRow("Description:", self.desc_edit)
        form.addRow("Author:", self.author_edit)
        form.addRow("Target Language:", self.lang_edit)
        # Model selection with reload button
        model_reload_layout = QHBoxLayout()
        model_reload_layout.addWidget(self.model_combo)
        
        self.reload_models_btn = QPushButton("↻")
        self.reload_models_btn.setToolTip("Reload models from config")
        self.reload_models_btn.setFixedWidth(30)
        self.reload_models_btn.clicked.connect(self.reload_models)
        model_reload_layout.addWidget(self.reload_models_btn)
        
        form.addRow("Model:", model_reload_layout)
        form.addRow("Context Limit:", self.limit_edit)
        form.addRow(QLabel("<b>Prompt Templates</b>"))
        form.addRow("Pre-Context System Prompt:", self.pre_system_prompt_edit)
        form.addRow("Post-Context System Prompt:", self.post_system_prompt_edit)
        form.addRow("User Prompt:", self.user_prompt_edit)
        
        # Context selection mode
        form.addRow(QLabel("<b>Context Selection</b>"))
        self.context_mode_combo = QComboBox()
        modes = [
            ("Automatic (Fill Budget)", "fill_budget"),
            ("Automatic (Strict Nearby)", "nearby"),
            ("Manual (Checkboxes)", "manual")
        ]
        
        # Add all modes with tooltips
        for text, mode_id in modes:
            self.context_mode_combo.addItem(text)
            
        # Set current mode
        current_mode = self.data.get("context_selection_mode", "fill_budget")
        if current_mode == "manual":
            self.context_mode_combo.setCurrentText("Manual (Checkboxes)")
        elif current_mode == "nearby":
            self.context_mode_combo.setCurrentText("Automatic (Strict Nearby)")
        else:
            self.context_mode_combo.setCurrentText("Automatic (Fill Budget)")
            
        form.addRow("Context Mode:", self.context_mode_combo)

        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def reload_models(self):
        """Reload models from config and update combo box"""
        if not self.model_manager:
            return
            
        success, message = self.model_manager.reload_models()
        if success:
            current_selection = self.model_combo.currentText()
            self.model_combo.clear()
            
            models = self.model_manager.get_all_models()
            for model_name in models:
                self.model_combo.addItem(model_name)
                
            # Restore selection if still available
            if current_selection in models:
                self.model_combo.setCurrentText(current_selection)
                
            QMessageBox.information(self, "Models Reloaded", message)
        else:
            QMessageBox.warning(self, "Reload Failed", message)

    def get_data(self):
        # Always include prompt_config with current values
        prompt_config = {
            "pre_system_prompt": self.pre_system_prompt_edit.toPlainText().strip(),
            "post_system_prompt": self.post_system_prompt_edit.toPlainText().strip(),
            "user_prompt": self.user_prompt_edit.toPlainText().strip()
        }

        return {
            "title": self.title_edit.text(),
            "description": self.desc_edit.text(),
            "author": self.author_edit.text(),
            "target_language": self.lang_edit.text(),
            "model": self.model_combo.currentText(),
            "context_token_limit_approx": int(self.limit_edit.text() or -1),
            "context_selection_mode": {
                "Manual (Checkboxes)": "manual",
                "Automatic (Strict Nearby)": "nearby",
                "Automatic (Fill Budget)": "fill_budget"
            }.get(self.context_mode_combo.currentText(), "fill_budget"),
            "prompt_config": prompt_config
        }
