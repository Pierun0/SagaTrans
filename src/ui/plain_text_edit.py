from PyQt5.QtWidgets import QTextEdit, QApplication
from PyQt5.QtCore import Qt


class PlainTextEdit(QTextEdit):
    """Custom QTextEdit that only accepts plain text on paste."""
    def pasteEvent(self, event):
        clipboard = QApplication.clipboard()
        plain_text = clipboard.text()
        self.insertPlainText(plain_text)