import json
from PyQt5.QtWidgets import QMessageBox, QDialog, QDialogButtonBox, QVBoxLayout, QTextEdit, QLabel, QTabWidget, QWidget
from PyQt5.QtCore import QTimer
from data_manager import load_config_defaults
from ui.translation_state_manager import TranslationState
from ui.item_translation_buffer import ItemTranslationBuffer


class TranslationManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.active_translations = {}  # item_index -> ItemTranslationBuffer
        self.active_threads = {}  # item_index -> TranslationThread

    def _build_api_payload_for_item(self, item_index):
        """Build API payload for a specific item, overriding the current item index temporarily."""
        if item_index is None or not self.main_window.current_project_data:
            return None

        # Store the current item index temporarily
        original_item_index = self.main_window.current_item_index
        
        # Temporarily set the current item index to build the payload
        self.main_window.current_item_index = item_index
        
        # Build the payload using the existing method
        payload = self._build_api_payload()
        
        # Restore the original item index
        self.main_window.current_item_index = original_item_index
        
        return payload

    def _build_api_payload(self):
        if self.main_window.current_item_index is None or not self.main_window.current_project_data:
            QMessageBox.warning(self.main_window, "Translation", "No item selected or project loaded.")
            return None

        source_text = self.main_window.source_text_area.toPlainText().strip()
        target_language = self.main_window.current_project_data.get('target_language', '')
        model_name = self.main_window.current_project_data.get('model', '')
        context_limit = self.main_window.current_project_data.get('context_token_limit_approx', -1)
        prompt_config = self.main_window.current_project_data.get('prompt_config', {})

        if not all([source_text, target_language, model_name]):
            QMessageBox.warning(self.main_window, "Translation",
                              "Cannot translate. Ensure source text exists and project language/model are set.")
            return None

        config_defaults = self._load_config_defaults().get("default_prompts", {})

        pre_system_prompt_template = prompt_config.get("pre_system_prompt",
            config_defaults.get("pre_system_prompt",
                "You are a translation assistant. Translate the final user message into **{target_language}**."
            )
        )
        post_system_prompt_template = prompt_config.get("post_system_prompt",
            config_defaults.get("post_system_prompt",
                "IMPORTANT: Respond with *only* the translation of the final user message into **{target_language}**, nothing else."
            )
        )
        user_prompt_template = prompt_config.get("user_prompt",
            config_defaults.get("user_prompt", "{source_text}")
        )

        context_item_template = (
            "\n==================== CONTEXT ITEM START: {item_name} ====================\n"
            "Source Text ({item_name}):\n{source_text}\n"
            "{translation_section}"
            "==================== CONTEXT ITEM END: {item_name} ======================\n"
        )

        context_items_str = ""
        included_indices, _ = self.main_window._get_context_item_indices()
        context_token_count = 0

        context_indices_to_use = sorted([idx for idx in included_indices if idx != self.main_window.current_item_index])

        for i in context_indices_to_use:
            try:
                item = self.main_window.project_items[i]
                item_name = item.get("name", f"Item {i+1}")
                item_source = item.get("source_text", "").strip()
                item_translation = item.get("translated_text", "").strip()

                if item_source:
                    if item_translation:
                        translation_section = f"\nExisting Translation ({target_language}) for '{item_name}':\n{item_translation}\n"
                    else:
                        translation_section = f"\n(No existing translation for '{item_name}')\n"

                    context_item = context_item_template.format(
                        item_name=item_name,
                        source_text=item_source,
                        translation_section=translation_section
                    )
                    context_items_str += context_item
                    context_token_count += self.main_window.count_tokens(item_source) + self.main_window.count_tokens(item_translation)

            except IndexError:
                print(f"Warning: Index {i} out of range during context building.")
                continue

        pre_system_prompt = pre_system_prompt_template.format(target_language=target_language)
        post_system_prompt = post_system_prompt_template.format(target_language=target_language)

        system_prompt_parts = [pre_system_prompt]
        if context_items_str:
            system_prompt_parts.append("\nUse the following context from other items in the project to inform your translation:")
            system_prompt_parts.append(context_items_str)
        system_prompt_parts.append("\n" + post_system_prompt)

        final_system_prompt = "\n".join(system_prompt_parts)

        #final_user_prompt = user_prompt_template.format(target_language=target_language)
        if '{target_language}' in user_prompt_template:
            final_user_prompt = user_prompt_template.format(source_text=source_text, target_language=target_language)
        else:
            final_user_prompt = user_prompt_template.format(source_text=source_text)

        return {
            "model": model_name,
            "messages": [
                {"role": "system", "content": final_system_prompt},
                {"role": "user", "content": final_user_prompt}
            ],
            "stream": True,
            "Target_Language": target_language
        }

    def _load_config_defaults(self):
        return {"default_prompts": load_config_defaults()}

    def translate_current_item(self):
        if self.main_window.current_item_index is None or not self.main_window.current_project_data:
            QMessageBox.warning(self.main_window, "Translation", "No item selected or project loaded.")
            return

        # Check if item is already being translated
        if self.main_window.translation_state_manager.is_item_translating(self.main_window.current_item_index):
            QMessageBox.warning(self.main_window, "Translation", "This item is already being translated.")
            return
            
        # Start translation for this specific item
        self.translate_item(self.main_window.current_item_index)
        
    def translate_item(self, item_index):
        """Start translation for a specific item."""
        if item_index is None or not self.main_window.current_project_data:
            QMessageBox.warning(self.main_window, "Translation", "No item selected or project loaded.")
            return

        # Check if item is already being translated
        if self.main_window.translation_state_manager.is_item_translating(item_index):
            QMessageBox.warning(self.main_window, "Translation", "This item is already being translated.")
            return

        # Get source text for the specific item
        if item_index == self.main_window.current_item_index:
            source_text = self.main_window.source_text_area.toPlainText().strip()
        else:
            # Get source text from project data for non-current items
            try:
                source_text = self.main_window.project_items[item_index].get('source_text', '').strip()
            except IndexError:
                QMessageBox.critical(self.main_window, "Error", f"Item index {item_index} out of range.")
                return
                
        if not source_text:
            QMessageBox.warning(self.main_window, "Translation", "Source text is empty.")
            return

        try:
            self.main_window.project_items[item_index]['source_text'] = source_text
        except IndexError:
            QMessageBox.critical(self.main_window, "Error", f"Item index {item_index} out of range.")
            return

        payload = self._build_api_payload_for_item(item_index)
        if not payload:
            return

        # Start translation state management for this specific item
        self.main_window.translation_state_manager.start_translation(item_index)
        
        # Create or get translation buffer for this item
        if item_index not in self.active_translations:
            buffer = ItemTranslationBuffer(item_index)
            self.active_translations[item_index] = buffer
        
        # If this is the currently selected item, clear the translated text area
        if item_index == self.main_window.current_item_index:
            self.main_window.translated_text_area.clear()
        
        from ui.translation_thread import TranslationThread
        
        # Create a unique thread for this item
        thread = TranslationThread(self.main_window, item_index)
        self.active_threads[item_index] = thread  # Store the thread

        thread.chunk_received.connect(
            lambda chunk: self._handle_translation_chunk_with_buffer(item_index, chunk)
        )
        thread.progress_updated.connect(self.main_window._handle_translation_progress)
        thread.finished.connect(
            lambda: self._handle_translation_finished_with_buffer(item_index)
        )
        thread.error.connect(self.main_window._handle_translation_error)

        thread.start()

    def stop_translation(self, item_index=None):
        """Stop translation for specific item or all items if item_index is None."""
        if item_index is not None:
            # Stop specific item
            self.stop_item_translation(item_index)
        else:
            # Stop all translations
            self.stop_all_translations()
            
    def stop_item_translation(self, item_index):
        """Stop translation for a specific item."""
        if item_index is None:
            return
            
        # Check if this item is being translated
        if not self.main_window.translation_state_manager.is_item_translating(item_index):
            return
            
        # Check if there's an active buffer for this item
        if item_index in self.active_translations:
            buffer = self.active_translations[item_index]
            buffer.stop()
            
        # Stop the thread if it exists
        if item_index in self.active_threads:
            thread = self.active_threads[item_index]
            if thread.isRunning():
                # Signal the thread to stop
                thread.stop()
                
                # Wait a short time for thread to stop gracefully
                if not thread.wait(1000):  # Wait up to 1 second
                    # If thread is still running, terminate it forcefully
                    if thread.isRunning():
                        thread.terminate()
                        thread.wait(500)  # Wait a bit more for termination
                
            # Clean up thread
            del self.active_threads[item_index]
            
        # Use state manager to handle stopping
        self.main_window.translation_state_manager.stop_translation(item_index)
            
        # Update UI state
        self.main_window._update_ui_state()
        
        # Update status bar
        item_name = self.main_window.project_items[item_index].get('name', f'Item {item_index + 1}')
        self.main_window.statusBar().showMessage(f"Translation for '{item_name}' stopped by user.", 3000)
        
        # Clean up translation buffer
        if item_index in self.active_translations:
            del self.active_translations[item_index]
            
    def stop_all_translations(self):
        """Stop all active translations."""
        # Get all currently translating items
        translating_items = list(self.main_window.translation_state_manager.get_translating_items())
        
        # Stop each item
        for item_index in translating_items:
            self.stop_item_translation(item_index)
            
        # Update status bar
        self.main_window.statusBar().showMessage("All translations stopped by user.", 3000)

    def _handle_translation_chunk_with_buffer(self, item_index, chunk):
        """Handle translation chunk with buffering system"""
        # Add chunk to buffer if it exists
        if item_index in self.active_translations:
            buffer = self.active_translations[item_index]
            if buffer.add_chunk(chunk):
                # If user is currently viewing this item, show real-time progress
                if self.main_window.current_item_index == item_index:
                    # Prevent textChanged signal during streaming update
                    self.main_window._start_programmatic_text_update()
                    self.main_window.translated_text_area.blockSignals(True)
                    
                    # Move cursor to end before inserting text to ensure streaming appears at end
                    cursor = self.main_window.translated_text_area.textCursor()
                    cursor.movePosition(cursor.End)
                    self.main_window.translated_text_area.setTextCursor(cursor)
                    
                    # Insert the text chunk
                    self.main_window.translated_text_area.insertPlainText(chunk)
                    
                    # Ensure cursor is visible at the end
                    self.main_window.translated_text_area.ensureCursorVisible()
                    self.main_window.translated_text_area.blockSignals(False)
                    self.main_window._end_programmatic_text_update()
                else:
                    # User is not viewing this item, but we should update the status
                    self.main_window._update_status_bar()
        
        # Also store in response buffer for compatibility
        if not hasattr(self.main_window, '_response_buffer'):
            self.main_window._response_buffer = []
        self.main_window._response_buffer.append(chunk)

    def _handle_translation_finished_with_buffer(self, item_index):
        """Handle translation completion with buffering system"""
        try:
            # Stop streaming state tracking for this item
            # Note: We don't call _stop_streaming_state() here as it's global
            # We want other translations to continue if they're running
            
            # Get the complete text from buffer
            if item_index in self.active_translations:
                buffer = self.active_translations[item_index]
                buffer.complete()
                translated_text = buffer.get_full_text()
                
                # Save to project data only after translation is complete
                if 0 <= item_index < len(self.main_window.project_items):
                    self.main_window.project_items[item_index]['translated_text'] = translated_text
                    self.main_window.mark_dirty()
                
                # Clear from active translations
                del self.active_translations[item_index]
            else:
                # Fallback to existing method if buffer doesn't exist
                if item_index == self.main_window.current_item_index:
                    translated_text = self.main_window.translated_text_area.toPlainText().strip()
                else:
                    # For non-current items, we need to get the text from the buffer
                    translated_text = ""  # This shouldn't happen if buffer exists
                    
                if not 0 <= item_index < len(self.main_window.project_items):
                    raise IndexError(f"Invalid item index {item_index}")

                self.main_window.project_items[item_index]['translated_text'] = translated_text
                self.main_window.mark_dirty()

            if hasattr(self.main_window, '_response_buffer'):
                # Only clear the response buffer if this was the current item
                if item_index == self.main_window.current_item_index:
                    self.main_window.last_response = ''.join(self.main_window._response_buffer)
                    self.main_window._response_buffer = []

            # Use state manager to handle completion for this specific item
            self.main_window.translation_state_manager.complete_translation(item_index)
            
            # Update status bar with item-specific message
            item_name = self.main_window.project_items[item_index].get('name', f'Item {item_index + 1}')
            self.main_window.statusBar().showMessage(f"Translation for '{item_name}' completed", 3000)
        except Exception as e:
            error_msg = f"Failed to save translation: {e}"
            QMessageBox.critical(self.main_window, "Error", error_msg)

    def _handle_translation_error(self, error_msg):
        """Handle translation errors with detailed error analysis and recovery options"""
        # Detailed error analysis
        if "timeout" in error_msg.lower():
            detailed_msg = f"Connection timeout:\n{error_msg}\n\nCheck your network connection and Ollama server status."
        elif "model not found" in error_msg.lower():
            detailed_msg = f"Model error:\n{error_msg}\n\nVerify the model name and ensure it's pulled on your Ollama server."
        else:
            detailed_msg = f"Error:\n{error_msg}"

        # Show error dialog with more context
        msg_box = QMessageBox(self.main_window)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Translation Error")
        msg_box.setText(detailed_msg)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

        # Use state manager to handle error state
        self.main_window.translation_state_manager.handle_error()
        
        self.main_window.statusBar().showMessage("Translation failed - " + error_msg.split('\n')[0], 5000)

    def show_request_payload(self):
        if self.main_window.current_item_index is None or not self.main_window.current_project_data:
            QMessageBox.warning(self.main_window, "View Request", "No item selected or project loaded.")
            return

        payload = self._build_api_payload()
        if not payload:
            return

        try:
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("API Request Payload")
            dialog.resize(800, 600)

            layout = QVBoxLayout(dialog)
            tab_widget = QTabWidget()

            formatted_tab = QWidget()
            formatted_layout = QVBoxLayout(formatted_tab)
            formatted_label = QLabel("Formatted JSON Payload:")
            formatted_layout.addWidget(formatted_label)

            formatted_edit = QTextEdit()
            formatted_edit.setReadOnly(True)
            formatted_edit.setPlainText(json.dumps(payload, indent=4, ensure_ascii=False))
            formatted_layout.addWidget(formatted_edit)
            tab_widget.addTab(formatted_tab, "Formatted")

            raw_tab = QWidget()
            raw_layout = QVBoxLayout(raw_tab)
            raw_label = QLabel("Raw Unicode Payload:")
            raw_layout.addWidget(raw_label)

            raw_edit = QTextEdit()
            raw_edit.setReadOnly(True)
            raw_text = json.dumps(payload, indent=4, ensure_ascii=False)
            raw_edit.setPlainText(raw_text)
            raw_layout.addWidget(raw_edit)
            tab_widget.addTab(raw_tab, "Raw Unicode")

            escaped_tab = QWidget()
            escaped_layout = QVBoxLayout(escaped_tab)
            escaped_label = QLabel("Escaped Unicode (Debug View):")
            escaped_layout.addWidget(escaped_label)

            escaped_edit = QTextEdit()
            escaped_edit.setReadOnly(True)
            escaped_text = json.dumps(payload, indent=4, ensure_ascii=True)
            escaped_edit.setPlainText(escaped_text)
            escaped_layout.addWidget(escaped_edit)
            tab_widget.addTab(escaped_tab, "Escaped Unicode")

            layout.addWidget(tab_widget)

            button_box = QDialogButtonBox(QDialogButtonBox.Close)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to show request payload:\n{e}")

    def show_last_response(self):
        if not hasattr(self.main_window, 'last_response') or self.main_window.last_response is None:
            QMessageBox.information(self.main_window, "Last Response", "No response has been received yet.")
            return

        try:
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("Last API Response")
            dialog.resize(800, 600)

            layout = QVBoxLayout(dialog)
            tab_widget = QTabWidget()

            formatted_tab = QWidget()
            formatted_layout = QVBoxLayout(formatted_tab)
            formatted_label = QLabel("Formatted Response:")
            formatted_layout.addWidget(formatted_label)

            formatted_edit = QTextEdit()
            formatted_edit.setReadOnly(True)
            try:
                response_data = json.loads(self.main_window.last_response)
                formatted_edit.setPlainText(json.dumps(response_data, indent=4, ensure_ascii=False))
            except json.JSONDecodeError:
                formatted_edit.setPlainText(str(self.main_window.last_response))
            formatted_layout.addWidget(formatted_edit)
            tab_widget.addTab(formatted_tab, "Formatted")

            raw_tab = QWidget()
            raw_layout = QVBoxLayout(raw_tab)
            raw_label = QLabel("Raw Text Response:")
            raw_layout.addWidget(raw_label)

            raw_edit = QTextEdit()
            raw_edit.setReadOnly(True)
            raw_edit.setPlainText(str(self.main_window.last_response))
            raw_layout.addWidget(raw_edit)
            tab_widget.addTab(raw_tab, "Raw Text")

            layout.addWidget(tab_widget)

            button_box = QDialogButtonBox(QDialogButtonBox.Close)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to show response:\n{e}")