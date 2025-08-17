from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QMessageBox

class ProjectSelectionDialog(QDialog):
    def __init__(self, parent=None, project_files=None):
        super().__init__(parent)
        self.setWindowTitle("Select Project")
        self.selected_project = None

        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        if project_files:
            self.list_widget.addItems(project_files)
        layout.addWidget(self.list_widget)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept_selection)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def accept_selection(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a project.")
            return
        self.selected_project = selected_items[0].text()
        self.accept()

    def get_selected_project(self):
        return self.selected_project
