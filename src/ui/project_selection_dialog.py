import os
import json
import shutil
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QMessageBox, QPushButton, QHBoxLayout, QFileDialog, QInputDialog

class ProjectSelectionDialog(QDialog):
    def __init__(self, parent=None, project_files=None):
        super().__init__(parent)
        self.setWindowTitle("Select Project")
        self.selected_project = None

        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        if project_files:
            self.list_widget.addItems(project_files)
        self.list_widget.itemSelectionChanged.connect(self.update_button_states)
        layout.addWidget(self.list_widget)

        # Project operation buttons
        button_layout = QHBoxLayout()
        
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_project)
        
        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self.duplicate_project)
        
        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self.rename_project)
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_project)
        
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.import_project)
        
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.duplicate_button)
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.import_button)
        
        layout.addLayout(button_layout)

        # OK/Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept_selection)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)
        
        # Update button states
        self.update_button_states()

    def accept_selection(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a project.")
            return
        self.selected_project = selected_items[0].text()
        self.accept()

    def update_button_states(self):
        has_selection = len(self.list_widget.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)
        self.duplicate_button.setEnabled(has_selection)
        self.rename_button.setEnabled(has_selection)
        self.export_button.setEnabled(has_selection)

    def remove_project(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
            
        project_name = selected_items[0].text()
        reply = QMessageBox.question(self, "Confirm Removal",
                                   f"Are you sure you want to delete '{project_name}'?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                projects_dir = "projects"
                filepath = os.path.join(projects_dir, project_name)
                
                if os.path.exists(filepath):
                    os.remove(filepath)
                    self.list_widget.takeItem(self.list_widget.row(selected_items[0]))
                    QMessageBox.information(self, "Success", f"Project '{project_name}' has been removed.")
                    self.update_button_states()
                else:
                    QMessageBox.warning(self, "Error", f"Project file '{project_name}' not found.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove project '{project_name}':\n{e}")

    def duplicate_project(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
            
        original_name = selected_items[0].text()
        original_name_without_ext = os.path.splitext(original_name)[0]
        
        new_name, ok = QInputDialog.getText(self, "Duplicate Project",
                                          f"Enter new project name (original: {original_name_without_ext}):",
                                          text=original_name_without_ext + "_copy")
        
        if ok and new_name:
            try:
                projects_dir = "projects"
                original_filepath = os.path.join(projects_dir, original_name)
                new_filename = new_name + ".json"
                new_filepath = os.path.join(projects_dir, new_filename)
                
                if os.path.exists(new_filepath):
                    QMessageBox.warning(self, "Error", f"A project named '{new_filename}' already exists.")
                    return
                
                if os.path.exists(original_filepath):
                    shutil.copy2(original_filepath, new_filepath)
                    self.list_widget.addItem(new_filename)
                    QMessageBox.information(self, "Success", f"Project '{original_name}' duplicated as '{new_filename}'.")
                    self.update_button_states()
                else:
                    QMessageBox.warning(self, "Error", f"Original project file '{original_name}' not found.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to duplicate project:\n{e}")

    def rename_project(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
            
        old_name = selected_items[0].text()
        old_name_without_ext = os.path.splitext(old_name)[0]
        
        new_name, ok = QInputDialog.getText(self, "Rename Project",
                                          f"Enter new project name (current: {old_name_without_ext}):",
                                          text=old_name_without_ext)
        
        if ok and new_name:
            try:
                projects_dir = "projects"
                old_filepath = os.path.join(projects_dir, old_name)
                new_filename = new_name + ".json"
                new_filepath = os.path.join(projects_dir, new_filename)
                
                if os.path.exists(new_filepath):
                    QMessageBox.warning(self, "Error", f"A project named '{new_filename}' already exists.")
                    return
                
                if os.path.exists(old_filepath):
                    # Rename the file
                    os.rename(old_filepath, new_filepath)
                    
                    # Update the project title in the JSON file
                    try:
                        with open(new_filepath, 'r', encoding='utf-8') as f:
                            project_data = json.load(f)
                        
                        project_data['title'] = new_name
                        
                        with open(new_filepath, 'w', encoding='utf-8') as f:
                            json.dump(project_data, f, indent=4)
                            
                    except Exception as json_e:
                        QMessageBox.warning(self, "Warning", f"File renamed but failed to update project title:\n{json_e}")
                    
                    # Update the list widget
                    self.list_widget.takeItem(self.list_widget.row(selected_items[0]))
                    self.list_widget.addItem(new_filename)
                    QMessageBox.information(self, "Success", f"Project renamed to '{new_filename}'.")
                    self.update_button_states()
                else:
                    QMessageBox.warning(self, "Error", f"Project file '{old_name}' not found.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename project:\n{e}")

    def export_project(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
            
        project_name = selected_items[0].text()
        
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Project",
                                                project_name,
                                                "JSON Files (*.json);;All Files (*)",
                                                options=options)
        
        if filepath:
            try:
                projects_dir = "projects"
                source_filepath = os.path.join(projects_dir, project_name)
                
                if os.path.exists(source_filepath):
                    shutil.copy2(source_filepath, filepath)
                    QMessageBox.information(self, "Success", f"Project '{project_name}' exported successfully.")
                else:
                    QMessageBox.warning(self, "Error", f"Project file '{project_name}' not found.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export project:\n{e}")

    def import_project(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Project",
                                                "",
                                                "JSON Files (*.json);;All Files (*)",
                                                options=options)
        
        if filepath:
            try:
                projects_dir = "projects"
                filename = os.path.basename(filepath)
                dest_filepath = os.path.join(projects_dir, filename)
                
                if os.path.exists(dest_filepath):
                    reply = QMessageBox.question(self, "File Exists",
                                               f"A project named '{filename}' already exists. Overwrite?",
                                               QMessageBox.Yes | QMessageBox.No,
                                               QMessageBox.No)
                    if reply == QMessageBox.No:
                        return
                
                shutil.copy2(filepath, dest_filepath)
                
                # Validate imported file
                try:
                    with open(dest_filepath, 'r', encoding='utf-8') as f:
                        json.load(f)  # Just validate it's valid JSON
                except Exception as e:
                    os.remove(dest_filepath)  # Remove corrupted file
                    QMessageBox.critical(self, "Error", f"Invalid project file format:\n{e}")
                    return
                
                self.list_widget.addItem(filename)
                QMessageBox.information(self, "Success", f"Project '{filename}' imported successfully.")
                self.update_button_states()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import project:\n{e}")

    def get_selected_project(self):
        return self.selected_project
