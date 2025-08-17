import copy
from PyQt5.QtWidgets import QMessageBox, QInputDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class ItemManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def add_item(self):
        if not self.main_window.current_project_data: return
        item_name, ok = QInputDialog.getText(self.main_window, "Add Item", "Enter name for the new item:")
        if ok and item_name:
            item_name = item_name.strip()
            if not item_name: return
            if any(item.get('name') == item_name for item in self.main_window.project_items):
                QMessageBox.warning(self.main_window, "Add Item", f"An item named '{item_name}' already exists.")
                return

            new_item = {"name": item_name, "source_text": "", "translated_text": ""}
            self.main_window.project_items.append(new_item)
            self.main_window._refresh_listbox_display()
            self.main_window.item_listbox.setCurrentRow(len(self.main_window.project_items) - 1)
            self.main_window._update_token_counts()
            self.main_window.mark_dirty()
        elif ok and not item_name:
             QMessageBox.warning(self.main_window, "Add Item", "Item name cannot be empty.")

    def remove_item(self):
        if self.main_window.current_item_index is None or not self.main_window.current_project_data: return
        try:
            item_name = self.main_window.project_items[self.main_window.current_item_index].get("name", f"Item {self.main_window.current_item_index + 1}")
            reply = QMessageBox.question(self.main_window, "Remove Item", f"Are you sure you want to remove '{item_name}'?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                del self.main_window.project_items[self.main_window.current_item_index]
                self.main_window.current_item_index = None
                self.main_window._refresh_listbox_display()
                self.main_window._update_token_counts()
                self.main_window.mark_dirty()
        except IndexError:
            QMessageBox.critical(self.main_window, "Error", "Failed to remove item: Index out of range.")
            self.main_window.current_item_index = None
            self.main_window._refresh_listbox_display()

    def rename_item(self):
        if self.main_window.current_item_index is None or not self.main_window.current_project_data: return
        try:
            current_name = self.main_window.project_items[self.main_window.current_item_index].get("name", "")
            new_name, ok = QInputDialog.getText(self.main_window, "Rename Item", "Enter new name:", text=current_name)
            if ok and new_name:
                new_name = new_name.strip()
                if not new_name:
                     QMessageBox.warning(self.main_window, "Rename Item", "Item name cannot be empty.")
                     return
                if new_name == current_name: return

                if any(item.get('name') == new_name for i, item in enumerate(self.main_window.project_items) if i != self.main_window.current_item_index):
                    QMessageBox.warning(self.main_window, "Rename Item", f"An item named '{new_name}' already exists.")
                    return

                self.main_window.project_items[self.main_window.current_item_index]['name'] = new_name
                self.main_window._refresh_listbox_display()
                self.main_window.mark_dirty()
            elif ok and not new_name:
                 QMessageBox.warning(self.main_window, "Rename Item", "Item name cannot be empty.")

        except IndexError:
            QMessageBox.critical(self.main_window, "Error", "Failed to rename item: Index out of range.")
            self.main_window.current_item_index = None
            self.main_window._refresh_listbox_display()

    def duplicate_item(self):
        if self.main_window.current_item_index is None or not self.main_window.current_project_data: return
        try:
            original_item = self.main_window.project_items[self.main_window.current_item_index]
            new_item = copy.deepcopy(original_item)

            base_name = new_item.get('name', 'Untitled')
            new_name = f"{base_name} Copy"
            existing_names = {item.get('name') for item in self.main_window.project_items}
            suffix = 2
            while new_name in existing_names:
                new_name = f"{base_name} Copy {suffix}"
                suffix += 1
            new_item['name'] = new_name

            insert_index = self.main_window.current_item_index + 1
            self.main_window.project_items.insert(insert_index, new_item)

            self.main_window._refresh_listbox_display()
            self.main_window.item_listbox.setCurrentRow(insert_index)
            self.main_window.mark_dirty()

        except IndexError:
            QMessageBox.critical(self.main_window, "Error", "Failed to duplicate item: Index out of range.")
            self.main_window.current_item_index = None
            self.main_window._refresh_listbox_display()
        except Exception as e:
             QMessageBox.critical(self.main_window, "Error", f"Failed to duplicate item: {e}")

    def move_item(self, direction):
        if self.main_window.current_item_index is None or not self.main_window.current_project_data: return
        current_index = self.main_window.current_item_index
        if direction == 'up' and current_index > 0:
            new_index = current_index - 1
        elif direction == 'down' and current_index < len(self.main_window.project_items) - 1:
            new_index = current_index + 1
        else:
            return

        self.main_window.project_items[current_index], self.main_window.project_items[new_index] = self.main_window.project_items[new_index], self.main_window.project_items[current_index]

        self.main_window.current_item_index = new_index
        self.main_window._refresh_listbox_display()
        self.main_window._update_token_counts()
        self.main_window.mark_dirty()

    def move_item_up(self):
        self.move_item('up')

    def move_item_down(self):
        self.move_item('down')

    def update_move_button_states(self):
        list_count = self.main_window.item_listbox.count()
        can_move_up = self.main_window.current_item_index is not None and self.main_window.current_item_index > 0
        can_move_down = self.main_window.current_item_index is not None and self.main_window.current_item_index < list_count - 1

        self.main_window.move_item_up_button.setEnabled(can_move_up)
        self.main_window.move_item_down_button.setEnabled(can_move_down)

    def _refresh_listbox_display(self):
        self.main_window.item_listbox.blockSignals(True)
        self.main_window.item_listbox.clear()
        current_selection_row = self.main_window.current_item_index
        included_indices, excluded_indices = self.main_window._get_context_item_indices()

        for i, item in enumerate(self.main_window.project_items):
            name = item.get("name", f"Item {i+1}")
            source_tokens = self.main_window.count_tokens(item.get('source_text', ''))
            target_tokens = self.main_window.count_tokens(item.get('translated_text', ''))
            display_text = f"{i + 1}. {name.ljust(40)} S:{source_tokens:4} T:{target_tokens:4}"

            list_item = self.main_window.item_listbox.item(i) if i < self.main_window.item_listbox.count() else None
            if not list_item:
                from PyQt5.QtWidgets import QListWidgetItem
                list_item = QListWidgetItem()
                self.main_window.item_listbox.addItem(list_item)

            list_item.setText(display_text)

            # Add checkbox if in manual context mode
            if self.main_window.current_project_data and self.main_window.current_project_data.get("context_selection_mode") == "manual":
                 list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
                 # Set initial checked state based on item data, default to checked if key doesn't exist
                 is_checked = item.get("include_in_context", True)
                 list_item.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)
            else:  
                 # Ensure no checkbox if not in manual mode
                 list_item.setFlags(list_item.flags() & ~Qt.ItemIsUserCheckable)
                 list_item.setCheckState(Qt.Unchecked) # Clear check state

            if i == self.main_window.current_item_index:
                list_item.setBackground(QColor(255, 165, 0))
            elif i in included_indices:
                list_item.setBackground(QColor(144, 238, 144))
            elif i in excluded_indices:
                list_item.setBackground(Qt.lightGray)
            else:
                list_item.setBackground(Qt.white)

        if current_selection_row is not None and 0 <= current_selection_row < self.main_window.item_listbox.count():
            self.main_window.item_listbox.setCurrentRow(current_selection_row)
        else:
             self.main_window.current_item_index = None
             self.main_window.source_text_area.clear()
             self.main_window.translated_text_area.clear()

        self.main_window.item_listbox.blockSignals(False)
        self.main_window._update_ui_state()

    def _update_listbox_item_display(self, index):
        if 0 <= index < len(self.main_window.project_items) and 0 <= index < self.main_window.item_listbox.count():
            item_data = self.main_window.project_items[index]
            name = item_data.get("name", f"Item {index + 1}")
            source_tokens = self.main_window.count_tokens(item_data.get('source_text', ''))
            target_tokens = self.main_window.count_tokens(item_data.get('translated_text', ''))
            display_text = f"{index + 1}. {name.ljust(40)} S:{source_tokens:4} T:{target_tokens:4}"
            list_item = self.main_window.item_listbox.item(index)
            if list_item:
                list_item.setText(display_text)
                included_indices, excluded_indices = self.main_window._get_context_item_indices()
                if index == self.main_window.current_item_index:
                    list_item.setBackground(QColor(255, 165, 0))  # Orange for current item
                elif index in included_indices:
                    list_item.setBackground(QColor(144, 238, 144))  # Light green for included context
                elif index in excluded_indices:
                    list_item.setBackground(Qt.lightGray)  # Light gray for excluded context
                else:
                    list_item.setBackground(Qt.white)  # White for normal items