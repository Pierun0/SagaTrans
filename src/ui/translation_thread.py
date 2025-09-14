from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from model_request_handler import ModelRequestHandler
from openrouter_adapter import OpenRouterAdapter
import time
import socket
import requests.exceptions


class TranslationThread(QThread):
    chunk_received = pyqtSignal(str)
    progress_updated = pyqtSignal(int, str)  # progress_percent, status_message
    finished = pyqtSignal()
    error = pyqtSignal(str)
    validation_failed = pyqtSignal(str)
    timeout_detected = pyqtSignal(str)

    def __init__(self, parent, item_index=None):
        super().__init__(parent)
        self.parent_window = parent
        self.item_index = item_index
        self.handler = None
        self.stop_requested = False
        self.model_manager = parent.model_manager if hasattr(parent, 'model_manager') else None
        self.timeout_timer = None
        self.last_activity_time = None
        self.request_timeout = 60  # Default timeout in seconds
        self.connection_check_interval = 5000  # 5 seconds for connection check

    def stop(self):
        """Request the translation to stop gracefully."""
        self.stop_requested = True
        # Stop the timeout timer
        if self.timeout_timer:
            self.timeout_timer.stop()
            self.timeout_timer = None
        # Reset last activity time
        self.last_activity_time = None
        if self.handler:
            try:
                self.handler.close()  # If handler has a close method
                # Force interrupt the handler if it's still streaming
                if hasattr(self.handler, 'interrupt'):
                    self.handler.interrupt()
            except:
                pass

    def _start_timeout_monitor(self):
        """Start monitoring for translation timeout."""
        self.last_activity_time = time.time()
        if self.timeout_timer:
            self.timeout_timer.stop()
        
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self._check_timeout)
        self.timeout_timer.start(self.connection_check_interval)  # Check every 5 seconds

    def _stop_timeout_monitor(self):
        """Stop monitoring for translation timeout."""
        if self.timeout_timer:
            self.timeout_timer.stop()
            self.timeout_timer = None

    def _check_timeout(self):
        """Check if translation has timed out."""
        if self.last_activity_time and time.time() - self.last_activity_time > self.request_timeout:
            timeout_msg = f"Translation timed out after {self.request_timeout} seconds"
            self.timeout_detected.emit(timeout_msg)
            self.stop()

    def _update_activity(self):
        """Update last activity time."""
        self.last_activity_time = time.time()

    def _categorize_error(self, error_msg):
        """Categorize the error type for better handling."""
        error_lower = error_msg.lower()
        
        # OpenRouter specific 403 errors
        if any(keyword in error_lower for keyword in ['openrouter api key error', 'openrouter quota exceeded', 'openrouter model access denied', 'openrouter access denied']):
            return "openrouter_403"
        # Network/timeout errors
        elif any(keyword in error_lower for keyword in ['timeout', 'connection', 'network', 'socket', 'requests']):
            return "network"
        # Model errors
        elif any(keyword in error_lower for keyword in ['model not found', 'invalid model', 'authentication', 'unauthorized']):
            return "model"
        # General errors
        else:
            return "general"

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

            # Start timeout monitoring
            self._start_timeout_monitor()

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
                        
                    # Update activity and emit chunk
                    self._update_activity()
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
            except requests.exceptions.Timeout as timeout_error:
                if not self.stop_requested:
                    error_type = self._categorize_error(str(timeout_error))
                    if error_type == "network":
                        self.timeout_detected.emit(f"Network timeout: {str(timeout_error)}")
                    else:
                        self.error.emit(f"Translation timeout: {str(timeout_error)}")
            except requests.exceptions.ConnectionError as conn_error:
                if not self.stop_requested:
                    self.error.emit(f"Connection error: {str(conn_error)}")
            except Exception as e:
                if self.stop_requested:
                    self.progress_updated.emit(0, "Translation stopped by user")
                    return
                else:
                    error_type = self._categorize_error(str(e))
                    if error_type == "openrouter_403":
                        self.error.emit(f"OpenRouter authentication error: {str(e)}")
                    elif error_type == "network":
                        self.timeout_detected.emit(f"Network error: {str(e)}")
                    else:
                        self.error.emit(f"Translation error: {str(e)}")
        except Exception as e:
            if not self.stop_requested:
                error_type = self._categorize_error(str(e))
                if error_type == "openrouter_403":
                    self.error.emit(f"OpenRouter authentication error: {str(e)}")
                elif error_type == "network":
                    self.timeout_detected.emit(f"Network error: {str(e)}")
                else:
                    self.error.emit(f"Translation error: {str(e)}")
            else:
                self.progress_updated.emit(0, "Translation stopped")
        finally:
            # Always stop timeout monitoring
            self._stop_timeout_monitor()