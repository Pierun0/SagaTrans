import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox
)


class ApiKeyDialog(QDialog):
    def __init__(self, parent=None, current_key=""):
        super().__init__(parent)
        self.setWindowTitle("Set API Key")
        self.resize(400, 130)
        layout = QVBoxLayout(self)

        # Label to show currently loaded key (masked)
        self.loaded_key_label = QLabel(self)
        if current_key:
            masked_key = current_key[:4] + "****" if len(current_key) > 4 else current_key
            self.loaded_key_label.setText(f"Loaded API Key: {masked_key}")
        else:
            self.loaded_key_label.setText("No API Key loaded")
        layout.addWidget(self.loaded_key_label)

        self.api_key_edit = QLineEdit(self)
        self.api_key_edit.setText(current_key)
        self.api_key_edit.setPlaceholderText("Enter your OpenRouter API key here")
        layout.addWidget(self.api_key_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_api_key(self):
        return self.api_key_edit.text().strip()