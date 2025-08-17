from PyQt5.QtCore import QThread, pyqtSignal
from model_request_handler import ModelRequestHandler
from openrouter_adapter import OpenRouterAdapter


class TranslationThread(QThread):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    validation_failed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.handler = None
        self.stop_requested = False
        self.model_manager = parent.model_manager if hasattr(parent, 'model_manager') else None

    def stop(self):
        """Request the translation to stop gracefully."""
        self.stop_requested = True
        if self.handler:
            try:
                self.handler.close()  # If handler has a close method
            except:
                pass

    def run(self):
        try:
            payload = self.parent_window._build_api_payload()
            if not payload:
                self.error.emit("Failed to build API payload.")
                return

            model_id = payload["model"]
            model_config = self.parent_window.model_manager.get_model_config(model_id) if self.parent_window.model_manager else None
            if not model_config:
                self.error.emit(f"Invalid model configuration for {model_id}")
                return

            # Create appropriate handler with full model_id including provider prefix
            self.handler = ModelRequestHandler.create_handler(model_id, model_config)
            if not self.handler:
                self.error.emit(f"Unsupported model provider for {model_id}")
                return


            # Validate connection
            if not self.handler.validate_connection():
                self.validation_failed.emit(f"Could not connect to {model_id} provider")
                return

            # Process stream
            for chunk in self.handler.send_request(payload):
                if self.stop_requested:
                    return
                self.chunk_received.emit(chunk)
                
            self.finished.emit()
        except Exception as e:
            if not self.stop_requested:
                self.error.emit(f"Translation error: {str(e)}")