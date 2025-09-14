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
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.current_state = TranslationState.IDLE
        self.translating_items = set()  # Track multiple translating items
        self.lock_levels = LockLevel.NONE
        
    def add_translating_item(self, item_index):
        """Add an item to the set of translating items."""
        if item_index not in self.translating_items:
            self.translating_items.add(item_index)
            if self.current_state != TranslationState.TRANSLATING:
                self.current_state = TranslationState.TRANSLATING
            self.state_changed.emit(self.current_state)
            self.translating_item_changed.emit(item_index)
            
    def remove_translating_item(self, item_index):
        """Remove an item from the set of translating items."""
        if item_index in self.translating_items:
            self.translating_items.remove(item_index)
            if not self.translating_items:
                self.current_state = TranslationState.IDLE
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
            self.current_state = TranslationState.IDLE
            self.state_changed.emit(self.current_state)
            
    def handle_error(self, item_index=None):
        """Handle error for specific item or all items."""
        if item_index is not None:
            # Handle error for specific item
            if item_index in self.translating_items:
                self.remove_translating_item(item_index)
                self.lock_levels = LockLevel.NONE
                self.lock_levels_changed.emit(self.lock_levels)
                
                # If no more items are translating, reset to idle
                if not self.translating_items:
                    QTimer.singleShot(2000, self.reset_idle)
        else:
            # Handle error for all items
            self.current_state = TranslationState.ERROR
            self.translating_items.clear()
            self.lock_levels = LockLevel.NONE
            self.state_changed.emit(self.current_state)
            self.lock_levels_changed.emit(self.lock_levels)
            self.translating_item_changed.emit(None)
            QTimer.singleShot(2000, self.reset_idle)
        
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