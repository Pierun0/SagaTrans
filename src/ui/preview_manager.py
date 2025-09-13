from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


class PreviewManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def toggle_live_preview_panel(self):
        if not QWebEngineView:
            QMessageBox.warning(self.main_window, "Live Preview", "QWebEngineView component is not available. Cannot show live preview.")
            self.main_window.toggle_live_preview_action.setChecked(False)
            return

        self.main_window.preview_visible = not self.main_window.preview_visible
        self.main_window.preview_frame.setVisible(self.main_window.preview_visible)
        self.main_window.toggle_live_preview_action.setChecked(self.main_window.preview_visible)

        if self.main_window.preview_visible:
            self.main_window._schedule_source_text_preview_update()
            self.main_window._schedule_translated_text_preview_update()
            self.main_window._sync_source_scroll_to_preview()
            self.main_window._sync_target_scroll_to_preview()

    def _sync_scroll_to_preview(self, text_edit, preview_view):
        if not self.main_window.preview_visible or not QWebEngineView or not preview_view:
            return

        scrollbar = text_edit.verticalScrollBar()
        max_scroll = scrollbar.maximum()
        current_scroll = scrollbar.value()

        scroll_fraction = 0.0
        scroll_fraction = 0.0
        if max_scroll > 0:
            scroll_fraction = current_scroll / max_scroll

        if self.main_window._scroll_sync_timer is None: # Check if timer is None
            self.main_window._scroll_sync_timer = QTimer()
            self.main_window._scroll_sync_timer.setSingleShot(True)
            self.main_window._scroll_sync_timer.timeout.connect(lambda f=scroll_fraction, pv=preview_view: self._execute_scroll_js(pv, f))
        else:
            self.main_window._scroll_sync_timer.stop()
            self.main_window._scroll_sync_timer.timeout.disconnect()
            self.main_window._scroll_sync_timer.timeout.connect(lambda f=scroll_fraction, pv=preview_view: self._execute_scroll_js(pv, f))

        self.main_window._scroll_sync_timer.start(50)

    def _sync_source_scroll_to_preview(self):
        if hasattr(self.main_window, 'source_text_preview'): # Check if source_text_preview exists
            self._sync_scroll_to_preview(self.main_window.source_text_area, self.main_window.source_text_preview)

    def _sync_target_scroll_to_preview(self):
        if hasattr(self.main_window, 'translated_text_preview'): # Check if translated_text_preview exists
            self._sync_scroll_to_preview(self.main_window.translated_text_area, self.main_window.translated_text_preview)

    def _update_preview_content(self, text_edit, preview_view):
        if not self.main_window.preview_visible or not QWebEngineView or not preview_view:
            return

        markdown_text = text_edit.toPlainText()

        try:
            import markdown2
            html = markdown2.markdown(markdown_text, extras=["fenced-code-blocks", "tables", "strike"])

            styled_html = f"""
            <html>
            <head>
            <style>
                body {{ font-family: sans-serif; padding: 10px; line-height: 1.6; font-size: 12px; }}
                h1 {{ font-size: 18px; }}
                h2 {{ font-size: 16px; }}
                h3 {{ font-size: 14px; }}
                h4, h5, h6 {{ font-size: 12px; }}
                p {{ margin-bottom: 0.8em; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 12px; }}
                code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: monospace; font-size: 12px; }}
                pre > code {{ background-color: transparent; padding: 0; border-radius: 0; }}
                blockquote {{ border-left: 4px solid #ccc; padding-left: 10px; color: #666; margin-left: 0; font-size: 12px; }}
                table {{ border-collapse: collapse; margin-bottom: 1em; width: auto; font-size: 12px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                img {{ max-width: 100%; height: auto; }}
                ul, ol {{ padding-left: 20px; font-size: 12px; }}
            </style>
            <script>
                function scrollToPercent(percentage) {{
                    const scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
                    const targetY = scrollableHeight * percentage;
                    window.scrollTo({{ top: targetY, behavior: 'auto' }});
                }}
            </script>
            </head>
            <body>{html}</body>
            </html>
            """

            preview_view.setHtml(styled_html)

        except Exception as e:
            error_html = f"<html><body>Error rendering Markdown:<br><pre>{e}</pre></body></html>"
            preview_view.setHtml(error_html)

    def _schedule_source_text_preview_update(self):
        if not QWebEngineView or not self.main_window.preview_visible:
            return

        if self.main_window._source_text_preview_timer is None:
            self.main_window._source_text_preview_timer = QTimer()
            self.main_window._source_text_preview_timer.setSingleShot(True)
            # Connect only if source_text_preview exists (which it should if QWebEngineView is available)
            if hasattr(self.main_window, 'source_text_preview') and self.main_window.source_text_preview:
                self.main_window._source_text_preview_timer.timeout.connect(lambda: self._update_preview_content(self.main_window.source_text_area, self.main_window.source_text_preview))
            else:
                 # If source_text_preview doesn't exist despite QWebEngineView, clean up timer
                 self.main_window._source_text_preview_timer = None
                 return

        self.main_window._source_text_preview_timer.start(300)

    def _schedule_translated_text_preview_update(self):
        if not QWebEngineView or not self.main_window.preview_visible:
            return

        if self.main_window._translated_text_preview_timer is None:
            self.main_window._translated_text_preview_timer = QTimer()
            self.main_window._translated_text_preview_timer.setSingleShot(True)
            # Connect only if translated_text_preview exists (which it should if QWebEngineView is available)
            if hasattr(self.main_window, 'translated_text_preview') and self.main_window.translated_text_preview:
                self.main_window._translated_text_preview_timer.timeout.connect(lambda: self._update_preview_content(self.main_window.translated_text_area, self.main_window.translated_text_preview))
            else:
                 # If translated_text_preview doesn't exist despite QWebEngineView, clean up timer
                 self.main_window._translated_text_preview_timer = None
                 return

        self.main_window._translated_text_preview_timer.start(300)
        
    def _execute_scroll_js(self, preview_view, scroll_fraction):
        """Execute JavaScript to scroll the preview to a specific fraction."""
        if preview_view and hasattr(preview_view, 'page') and preview_view.page():
            js_code = f"scrollToPercent({scroll_fraction});"
            preview_view.page().runJavaScript(js_code)