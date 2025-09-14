from PyQt5.QtCore import QThread, pyqtSignal
from model_request_handler import ModelRequestHandler
from openrouter_adapter import OpenRouterAdapter


class TranslationThread(QThread):
    chunk_received = pyqtSignal(str)
    progress_updated = pyqtSignal(int, str)  # progress_percent, status_message
    finished = pyqtSignal()
    error = pyqtSignal(str)
    validation_failed = pyqtSignal(str)

    def __init__(self, parent, item_index=None):
        super().__init__(parent)
        self.parent_window = parent
        self.item_index = item_index
        self.handler = None
        self.stop_requested = False
        self.model_manager = parent.model_manager if hasattr(parent, 'model_manager') else None

    def stop(self):
        """Request the translation to stop gracefully."""
        self.stop_requested = True
        if self.handler:
            try:
                self.handler.close()  # If handler has a close method
                # Force interrupt the handler if it's still streaming
                if hasattr(self.handler, 'interrupt'):
                    self.handler.interrupt()
            except:
                pass

    def run(self):
        try:
            # Use item-specific payload building if item_index is provided
            if self.item_index is not None:
                payload = self.parent_window.translation_manager._build_api_payload_for_item(self.item_index)
            else:
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

            # Process stream with progress tracking
            total_chunks = 0
            processed_chunks = 0
            
            # First pass: count total chunks (if possible) for progress calculation
            # Note: Some streaming APIs may not provide total count, so this is approximate
            try:
                # Try to estimate total chunks by checking content length
                content_length = len(payload.get("messages", [{}])[-1].get("content", ""))
                estimated_chunks = max(1, content_length // 100)  # Rough estimate
                total_chunks = estimated_chunks
            except:
                total_chunks = 1  # Fallback if estimation fails

            # Send the request and track progress
            try:
                for chunk in self.handler.send_request(payload):
                    if self.stop_requested:
                        self.progress_updated.emit(0, "Translation stopped by user")
                        return
                        
                    self.chunk_received.emit(chunk)
                    processed_chunks += 1
                    
                    # Calculate progress percentage
                    if total_chunks > 1:
                        progress_percent = min(95, int((processed_chunks / total_chunks) * 100))  # Cap at 95% until completion
                    else:
                        progress_percent = 50  # Mid-point for unknown total
                        
                    status_msg = f"Processing... {processed_chunks} chunks"
                    self.progress_updated.emit(progress_percent, status_msg)
                    
                self.progress_updated.emit(100, "Translation completed")
                self.finished.emit()
            except Exception as e:
                if self.stop_requested:
                    self.progress_updated.emit(0, "Translation stopped by user")
                    return
                else:
                    self.error.emit(f"Translation error: {str(e)}")
        except Exception as e:
            if not self.stop_requested:
                self.error.emit(f"Translation error: {str(e)}")
            else:
                self.progress_updated.emit(0, "Translation stopped")