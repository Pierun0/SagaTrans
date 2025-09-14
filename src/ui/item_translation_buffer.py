"""
ItemTranslationBuffer - Simple buffer for storing translation chunks for a specific item
"""

class ItemTranslationBuffer:
    """Simple buffer for storing translation chunks for a specific item"""
    def __init__(self, item_index):
        self.item_index = item_index
        self.chunks = []  # List of translation chunks
        self.is_complete = False
        self.is_stopped = False
        
    def add_chunk(self, chunk):
        """Add a translation chunk"""
        if not self.is_complete and not self.is_stopped:
            self.chunks.append(chunk)
            return True  # Chunk was added
        return False  # Buffer is complete or stopped
        
    def get_full_text(self):
        """Get complete translated text"""
        return ''.join(self.chunks)
        
    def complete(self):
        """Mark as complete"""
        self.is_complete = True
        
    def stop(self):
        """Mark as stopped"""
        self.is_stopped = True