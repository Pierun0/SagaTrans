from PyQt5.QtCore import QObject, pyqtSignal, QTimer


class TranslationState:
    IDLE = "idle"
    TRANSLATING = "translating"
    STOPPING = "stopping"
    COMPLETED = "completed"
    ERROR = "error"


class LockLevel:
    NONE = 0
    ITEM_SELECT = 1
    ITEM_MODIFY = 2
    TEXT_EDIT = 3
    PROJECT_OP = 4


class TranslationStateManager(QObject):
    state_changed = pyqtSignal(str)
    lock_levels_changed = pyqtSignal(int)
    translating_item_changed = pyqtSignal(int)
    ui_refresh_needed = pyqtSignal()
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_state = TranslationState.IDLE
        self.translating_items = set()  # Track multiple translating items
        self.lock_levels = LockLevel.NONE
        
    def add_translating_item(self, item_index):
        """Add an item to the set of translating items."""
        print(f"DEBUG: Adding item {item_index} to translating items. Current: {self.translating_items}")
        if item_index not in self.translating_items:
            self.translating_items.add(item_index)
            if self.current_state != TranslationState.TRANSLATING:
                self.current_state = TranslationState.TRANSLATING
            self.state_changed.emit(self.current_state)
            self.translating_item_changed.emit(item_index)
            print(f"DEBUG: Item {item_index} added. New translating items: {self.translating_items}")
            
    def remove_translating_item(self, item_index):
        """Remove an item from the set of translating items."""
        print(f"DEBUG: Removing item {item_index} from translating items. Current: {self.translating_items}")
        if item_index in self.translating_items:
            self.translating_items.remove(item_index)
            print(f"DEBUG: Item {item_index} removed. New translating items: {self.translating_items}")
            if not self.translating_items:
                self.current_state = TranslationState.IDLE
                print(f"DEBUG: No more translating items, setting state to IDLE")
            self.state_changed.emit(self.current_state)
            self.translating_item_changed.emit(item_index)
            
    def start_translation(self, item_index):
        """Start translation for a specific item."""
        self.add_translating_item(item_index)
        self.lock_levels = LockLevel.PROJECT_OP
        self.lock_levels_changed.emit(self.lock_levels)
        
    def stop_translation(self, item_index=None):
        """Stop translation for specific item or all items if item_index is None."""
        if item_index is not None:
            # Stop specific item
            if item_index in self.translating_items:
                self.remove_translating_item(item_index)
                self.lock_levels = LockLevel.NONE
                self.lock_levels_changed.emit(self.lock_levels)
        else:
            # Stop all translations
            if self.current_state == TranslationState.TRANSLATING:
                self.current_state = TranslationState.STOPPING
                self.translating_items.clear()
                self.lock_levels = LockLevel.NONE
                self.state_changed.emit(self.current_state)
                self.lock_levels_changed.emit(self.lock_levels)
                self.translating_item_changed.emit(None)
            
    def complete_translation(self, item_index=None):
        """Complete translation for specific item or all items."""
        if item_index is not None:
            # Complete specific item
            if item_index in self.translating_items:
                self.remove_translating_item(item_index)
                self.lock_levels = LockLevel.NONE
                self.lock_levels_changed.emit(self.lock_levels)
                
                # If no more items are translating, reset to idle after delay
                if not self.translating_items:
                    QTimer.singleShot(2000, self.reset_idle)
        else:
            # Complete all translations
            self.current_state = TranslationState.COMPLETED
            self.translating_items.clear()
            self.lock_levels = LockLevel.NONE
            self.state_changed.emit(self.current_state)
            self.lock_levels_changed.emit(self.lock_levels)
            self.translating_item_changed.emit(None)
            QTimer.singleShot(2000, self.reset_idle)
        
    def reset_idle(self):
        """Reset to idle state when no translations are active."""
        if self.current_state != TranslationState.IDLE:
            print(f"DEBUG: Resetting state from {self.current_state} to IDLE")
            self.current_state = TranslationState.IDLE
            self.state_changed.emit(self.current_state)
    
    def force_reset(self):
        """Force reset to idle state, used for recovery scenarios."""
        print("DEBUG: Forcing state reset to IDLE")
        print(f"DEBUG: Before reset - State: {self.current_state}, Translating items: {self.translating_items}")
        self.current_state = TranslationState.IDLE
        self.translating_items.clear()
        self.lock_levels = LockLevel.NONE
        print(f"DEBUG: After reset - State: {self.current_state}, Translating items: {self.translating_items}")
        self.state_changed.emit(self.current_state)
        self.lock_levels_changed.emit(self.lock_levels)
        self.translating_item_changed.emit(None)
        
        # Emit a special signal to indicate UI refresh is needed
        self.ui_refresh_needed.emit()
        print("DEBUG: UI refresh needed signal emitted")
            
    def handle_error(self, item_index=None, error_type=None):
        """Handle error for specific item or all items.
        
        Args:
            item_index: Specific item index that had the error, or None for all items
            error_type: Type of error (e.g., '403', 'timeout', 'network') for specialized handling
        """
        print(f"DEBUG: Handling error for item {item_index}, error_type: {error_type}, current state: {self.current_state}")
        print(f"DEBUG: Translating items before error handling: {self.translating_items}")
        
        # For 403 errors, ensure immediate and complete state reset
        if error_type == '403':
            print("DEBUG: 403 error detected - forcing immediate state reset")
            self.force_reset()
            return
        
        if item_index is not None:
            # Handle error for specific item
            if item_index in self.translating_items:
                self.remove_translating_item(item_index)
                self.lock_levels = LockLevel.NONE
                self.lock_levels_changed.emit(self.lock_levels)
                
                # If no more items are translating, reset to idle immediately
                if not self.translating_items:
                    self.reset_idle()
        else:
            # Handle error for all items
            self.current_state = TranslationState.ERROR
            self.translating_items.clear()
            self.lock_levels = LockLevel.NONE
            self.state_changed.emit(self.current_state)
            self.lock_levels_changed.emit(self.lock_levels)
            self.translating_item_changed.emit(None)
            # Reset to idle immediately instead of after delay
            self.reset_idle()
        
    def can_modify_items(self):
        return (self.current_state == TranslationState.IDLE and
                self.lock_levels <= LockLevel.ITEM_MODIFY)
                
    def can_edit_text(self):
        return (self.current_state == TranslationState.IDLE and
                self.lock_levels <= LockLevel.TEXT_EDIT)
                
    def can_select_items(self):
        return (self.current_state == TranslationState.IDLE and
                self.lock_levels <= LockLevel.ITEM_SELECT)
                
    def is_item_translating(self, item_index):
        """Check if specific item is being translated."""
        return item_index in self.translating_items
        
    def is_any_item_translating(self):
        """Check if any item is being translated."""
        return len(self.translating_items) > 0
                
    def is_item_locked(self, item_index):
        """Check if specific item is locked during translation."""
        return item_index in self.translating_items

    def should_lock_translate_button(self, item_index):
        """Check if translate button should be locked for a specific item."""
        return item_index in self.translating_items
        
    def get_translating_items(self):
        """Get all currently translating items."""
        return self.translating_items.copy()