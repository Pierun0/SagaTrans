import os
import json
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QDialog
import os
import shutil
import json
from ui.new_project_dialog import NewProjectDialog
from ui.project_selection_dialog import ProjectSelectionDialog


class ProjectManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def new_project(self):
        if not self.main_window._check_unsaved_changes():
            return

        dialog = NewProjectDialog(self.main_window)
        if dialog.exec_() == QDialog.Accepted:
            project_details = dialog.get_project_details()
            title = project_details["title"]
            filename = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
            filename = filename.replace(" ", "_") + ".json"
            projects_dir = "projects"
            if not os.path.exists(projects_dir):
                try:
                    os.makedirs(projects_dir)
                except OSError as e:
                     QMessageBox.critical(self.main_window, "Error", f"Failed to create projects directory:\n{e}")
                     return

            filepath = os.path.join(projects_dir, filename)

            if os.path.exists(filepath):
                QMessageBox.warning(self.main_window, "Error", f"Project file '{filename}' already exists in '{projects_dir}'.")
                return

            new_project_data = {
                "title": title,
                "description": project_details.get("description", ""),
                "author": project_details.get("author", ""),
                "target_language": project_details.get("target_language", ""),
                "model": project_details.get("model", "google/gemini-2.0-flash-exp:free"),
                "context_token_limit_approx": project_details.get("context_token_limit_approx", -1),
                "items": []
            }
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(new_project_data, f, indent=4)
                QMessageBox.information(self.main_window, "Success", f"Project '{title}' created as '{filename}'.")
                self.main_window.load_project_data(title, filename)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to create project file '{filepath}':\n{e}")

    def load_project(self):
        if not self.main_window._check_unsaved_changes():
            return

        projects_dir = "projects"
        if not os.path.isdir(projects_dir):
            QMessageBox.information(self.main_window, "Load Project", f"Projects directory '{projects_dir}' not found.")
            return

        project_files = [f for f in os.listdir(projects_dir) if f.endswith(".json") and os.path.isfile(os.path.join(projects_dir, f))]
        if not project_files:
            QMessageBox.information(self.main_window, "Load Project", f"No project files (.json) found in '{projects_dir}'.")
            return

        dialog = ProjectSelectionDialog(self.main_window, project_files)
        if dialog.exec_() == QDialog.Accepted:
            selected_filename = dialog.get_selected_project()
            if selected_filename:
                self.main_window.load_project_data(None, selected_filename)

    def load_project_data(self, project_title=None, project_filename=None):
        if not project_filename:
             QMessageBox.critical(self.main_window, "Error", "No project filename provided to load.")
             return

        projects_dir = "projects"
        filepath = os.path.join(projects_dir, project_filename)

        if not os.path.exists(filepath):
             QMessageBox.critical(self.main_window, "Error", f"Project file not found:\n{filepath}")
             return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                project_data = json.load(f)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self.main_window, "Load Error", f"Failed to read project file (invalid JSON):\n{filepath}\n{e}")
            return
        except Exception as e:
            QMessageBox.critical(self.main_window, "Load Error", f"Failed to load project file:\n{filepath}\n{e}")
            return

        self.main_window.current_project_data = project_data
        self.main_window.current_file = filepath
        
        # Ensure all required fields are present, even for old projects
        if 'author' not in self.main_window.current_project_data:
            self.main_window.current_project_data['author'] = ''
        if 'context_selection_mode' not in self.main_window.current_project_data:
            self.main_window.current_project_data['context_selection_mode'] = 'fill_budget'
        if 'prompt_config' not in self.main_window.current_project_data:
            self.main_window.current_project_data['prompt_config'] = {}
            
        self.main_window.project_items = self.main_window.current_project_data.get("items", [])
        self.main_window.current_item_index = None

        loaded_title = self.main_window.current_project_data.get("title", project_filename)
        if not project_title:
            project_title = loaded_title

        self.main_window.item_listbox.clear()
        self.main_window.source_text_area.clear()
        self.main_window.translated_text_area.clear()

        self.main_window._refresh_listbox_display()

        self.main_window.setWindowTitle(f"SagaTrans - {project_title}")
        self.main_window.statusBar().showMessage(f"Loaded project: {project_title}")
        self.main_window.is_dirty = False
        self.main_window._update_ui_state()

    def save_project(self):
        if not self.main_window.current_project_data or not self.main_window.current_file:
            QMessageBox.warning(self.main_window, "Save Project", "No project loaded or file path is missing.")
            return

        # Ensure the currently displayed text is saved before writing the whole file
        self.main_window._save_text_for_index(self.main_window.current_item_index)

        try:
            if 'items' not in self.main_window.current_project_data:
                self.main_window.current_project_data['items'] = []
            self.main_window.current_project_data['items'] = self.main_window.project_items

            with open(self.main_window.current_file, "w", encoding="utf-8") as f:
                json.dump(self.main_window.current_project_data, f, indent=4)

            self.main_window.is_dirty = False
            self.main_window._update_ui_state()
            self.main_window.statusBar().showMessage(f"Project saved to {self.main_window.current_file}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Save Error", f"Failed to save project to:\n{self.main_window.current_file}\n{e}")

    def edit_project_settings(self):
        if not self.main_window.current_project_data:
            QMessageBox.warning(self.main_window, "Edit Project", "No project loaded.")
            return

        from ui.qt_project_dialog import ProjectSettingsDialog
        dialog = ProjectSettingsDialog(self.main_window, self.main_window.current_project_data, self.main_window.model_manager)
        if dialog.exec_() == QDialog.Accepted:
            updated_settings = dialog.get_data()

            self.main_window.current_project_data.update({
                'title': updated_settings.get('title', ''),
                'description': updated_settings.get('description', ''),
                'author': updated_settings.get('author', ''),
                'target_language': updated_settings.get('target_language', ''),
                'model': updated_settings.get('model', ''),
                'context_token_limit_approx': updated_settings.get('context_token_limit_approx', -1),
                'context_selection_mode': updated_settings.get('context_selection_mode', 'fill_budget'),
                'prompt_config': updated_settings.get('prompt_config', {})
            })

            old_limit = self.main_window.current_project_data.get('context_token_limit_approx', -1)
            new_limit = updated_settings.get('context_token_limit_approx', -1)
            limit_changed = old_limit != new_limit

            old_mode = self.main_window.current_project_data.get('context_selection_mode', 'fill_budget')
            new_mode = updated_settings.get('context_selection_mode', 'fill_budget')
            mode_changed = old_mode != new_mode

            self.main_window.statusBar().showMessage("Project settings updated.")
            self.main_window.mark_dirty()

            if limit_changed or mode_changed:
                self.main_window._refresh_listbox_display()

            # Automatically save the project after updating settings
            self.save_project()
            QMessageBox.information(self.main_window, "Edit Project", "Project settings updated and saved.")

    def export_epub(self):
        """Handles the EPUB export process."""
        if not self.main_window.current_project_data:
            QMessageBox.warning(self.main_window, "Export EPUB", "No project loaded.")
            return

        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog # Uncomment if needed for debugging file dialog issues

        # Suggest a default filename based on project title
        default_filename = self.main_window.current_project_data.get('title', 'Exported_Project')
        default_filename = "".join(c for c in default_filename if c.isalnum() or c in (' ', '_', '-')).rstrip()
        default_filename = default_filename.replace(" ", "_") + ".epub"

        filepath, _ = QFileDialog.getSaveFileName(self.main_window, "Export Project as EPUB",
                                                  default_filename,
                                                  "EPUB Files (*.epub);;All Files (*)", options=options)

        if filepath:
            from epub_exporter import export_project_to_epub
            success, message = export_project_to_epub(self.main_window.current_project_data, filepath)
            if success:
                QMessageBox.information(self.main_window, "Export EPUB", f"Project successfully exported to:\n{filepath}")
            else:
                QMessageBox.critical(self.main_window, "Export EPUB Error", f"Failed to export EPUB:\n{message}")

    def remove_project_file(self, project_filename):
        """Remove a project file from the projects directory."""
        try:
            projects_dir = "projects"
            filepath = os.path.join(projects_dir, project_filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                return True, None
            else:
                return False, f"Project file '{project_filename}' not found."
        except Exception as e:
            return False, f"Failed to remove project '{project_filename}':\n{e}"

    def duplicate_project_file(self, source_filename, new_name):
        """Duplicate a project file with a new name."""
        try:
            projects_dir = "projects"
            source_filepath = os.path.join(projects_dir, source_filename)
            new_filename = new_name + ".json"
            new_filepath = os.path.join(projects_dir, new_filename)
            
            if os.path.exists(new_filepath):
                return False, f"A project named '{new_filename}' already exists."
            
            if os.path.exists(source_filepath):
                shutil.copy2(source_filepath, new_filepath)
                
                # Update the project title in the duplicated file
                try:
                    with open(new_filepath, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                    
                    project_data['title'] = new_name
                    
                    with open(new_filepath, 'w', encoding='utf-8') as f:
                        json.dump(project_data, f, indent=4)
                        
                except Exception as json_e:
                    # If title update fails, the file is still duplicated
                    pass
                
                return True, new_filename
            else:
                return False, f"Original project file '{source_filename}' not found."
        except Exception as e:
            return False, f"Failed to duplicate project:\n{e}"

    def rename_project_file(self, old_filename, new_name):
        """Rename a project file and update its title."""
        try:
            projects_dir = "projects"
            old_filepath = os.path.join(projects_dir, old_filename)
            new_filename = new_name + ".json"
            new_filepath = os.path.join(projects_dir, new_filename)
            
            if os.path.exists(new_filepath):
                return False, f"A project named '{new_filename}' already exists."
            
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
                    # If title update fails, the file is still renamed
                    pass
                
                return True, new_filename
            else:
                return False, f"Project file '{old_filename}' not found."
        except Exception as e:
            return False, f"Failed to rename project:\n{e}"

    def export_project_file(self, project_filename, export_path):
        """Export a project file to a specified location."""
        try:
            projects_dir = "projects"
            source_filepath = os.path.join(projects_dir, project_filename)
            
            if os.path.exists(source_filepath):
                shutil.copy2(source_filepath, export_path)
                return True, None
            else:
                return False, f"Project file '{project_filename}' not found."
        except Exception as e:
            return False, f"Failed to export project:\n{e}"

    def import_project_file(self, import_path):
        """Import a project file from a specified location."""
        try:
            projects_dir = "projects"
            filename = os.path.basename(import_path)
            dest_filepath = os.path.join(projects_dir, filename)
            
            # Check if file already exists
            if os.path.exists(dest_filepath):
                return False, f"A project named '{filename}' already exists.", None
            
            # Copy the file
            shutil.copy2(import_path, dest_filepath)
            
            # Validate the imported file
            try:
                with open(dest_filepath, 'r', encoding='utf-8') as f:
                    json.load(f)  # Just validate it's valid JSON
            except Exception as e:
                # Remove corrupted file
                if os.path.exists(dest_filepath):
                    os.remove(dest_filepath)
                return False, f"Invalid project file format:\n{e}", None
            
            return True, None, filename
        except Exception as e:
            return False, f"Failed to import project:\n{e}", None