class TokenManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def count_tokens(self, text: str) -> int:
        if not isinstance(text, str):
            text = ""

        cache_key = hash(text)
        if cache_key in self.main_window._token_cache:
            return self.main_window._token_cache[cache_key]

        token_count = 0
        if self.main_window.tokenizer:
            try:
                token_count = len(self.main_window.tokenizer.encode(text))
            except Exception as e:
                print(f"Tokenizer failed: {e}. Using fallback.")
                token_count = len(text) // 4
        else:
            token_count = len(text) // 4

        self.main_window._token_cache[cache_key] = token_count
        return token_count

    def _clear_token_cache(self):
        self.main_window._token_cache = {}
        self.main_window._cache_version += 1

    def _update_token_counts(self):
        if not self.main_window.current_project_data or getattr(self.main_window, '_updating_token_counts', False):
            return

        try:
            self.main_window._updating_token_counts = True
            self.main_window.source_text_area.blockSignals(True)
            self.main_window.translated_text_area.blockSignals(True)
            self.main_window.item_listbox.blockSignals(True)

            if not hasattr(self.main_window, 'item_listbox'):
                return

            for i in range(len(self.main_window.project_items)):
                item = self.main_window.project_items[i]
                source_tokens = self.count_tokens(item.get('source_text', ''))
                target_tokens = self.count_tokens(item.get('translated_text', ''))
 
                if i < self.main_window.item_listbox.count():
                    list_item = self.main_window.item_listbox.item(i)
                    item_number = i + 1 # Define item_number explicitly
                    display_text = f"{item_number}. {item.get('name', 'Item').ljust(40)} S:{source_tokens:4} T:{target_tokens:4}"
                    list_item.setText(display_text)
            
            if self.main_window.current_item_index is not None:
                self.main_window._save_text_for_index(self.main_window.current_item_index)


        except Exception as e:
            print(f"Warning: Could not update token counts: {e}")
        finally:
            self.main_window._updating_token_counts = False
            # Ensure signals are unblocked even if there was an error
            if hasattr(self.main_window, 'source_text_area'): self.main_window.source_text_area.blockSignals(False)
            if hasattr(self.main_window, 'translated_text_area'): self.main_window.translated_text_area.blockSignals(False)
            if hasattr(self.main_window, 'item_listbox'): self.main_window.item_listbox.blockSignals(False)

    def _delayed_update_token_counts(self):
        if not hasattr(self.main_window, '_debounce_timer'):
            from PyQt5.QtCore import QTimer
            self.main_window._debounce_timer = QTimer()
            self.main_window._debounce_timer.setSingleShot(True)
            self.main_window._debounce_timer.timeout.connect(self._update_token_counts)

        self.main_window._debounce_timer.start(500)

    def calculate_all_tokens(self):
        if not self.main_window.current_project_data:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.main_window, "Calculate Tokens", "No project loaded.")
            return

        total_tokens = 0
        for i, item in enumerate(self.main_window.project_items):
            source_tokens = self.count_tokens(item.get('source_text', ''))
            target_tokens = self.count_tokens(item.get('translated_text', ''))
            total_tokens += source_tokens + target_tokens
            
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self.main_window, "Total Token Count", f"Total approximate tokens for all items: {total_tokens}")