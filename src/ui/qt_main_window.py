import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QAction, QSplitter, QWidget, QVBoxLayout, QToolBar,
    QFileDialog, QMessageBox, QListWidget, QPushButton, QHBoxLayout, QInputDialog, QDialog, QLineEdit, QDialogButtonBox, QLabel,
    QListWidgetItem, QTabWidget, QComboBox, QSizePolicy, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QUrl
from PyQt5.QtGui import QColor, QClipboard
from model_request_handler import ModelRequestHandler
from openrouter_adapter import OpenRouterAdapter
import copy
import data_manager
from ui.project_selection_dialog import ProjectSelectionDialog

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
except ImportError as e:
    print(f"Failed to import QWebEngine components: {e}")
    QWebEngineView = None
    QWebEngineSettings = None
import markdown2
import json
import os
from ui.qt_project_dialog import ProjectSettingsDialog
import tiktoken
from epub_exporter import export_project_to_epub # Import the new exporter

# Import the new manager classes
from ui.project_manager import ProjectManager
from ui.item_manager import ItemManager
from ui.preview_manager import PreviewManager
from ui.translation_manager import TranslationManager
from ui.token_manager import TokenManager
from ui.plain_text_edit import PlainTextEdit
from ui.translation_thread import TranslationThread

class QtMainWindow(QMainWindow):
    # Application version
    VERSION = "0.1.0"
    
    def __init__(self, model_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"SagaTrans v{self.VERSION}")
        self.model_manager = model_manager
        self.resize(1200, 800)

        # Connect signals for context updates
        self._context_update_signals = [
            'current_item_index',
            'project_items',
            'current_project_data'
        ]

        # Token count cache
        self._token_cache = {}
        self._cache_version = 0
        self.project_metadata = {}
        self.project_items = []  # List of dicts with keys: name, source_text, translated_text, approx_token_count
        self.current_item_index = None
        self.tokenizer = None
        self.current_file = None
        self.is_dirty = False # Track unsaved changes
        self.current_project_data = None # Moved this line up
        try:
            import tiktoken
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            print(f"Warning: Tokenizer init failed: {e}")

        # Preview-related attributes
        self.preview_visible = False
        self._debounce_timer = None # For token counts (Kept for potential future use, but disconnected from text edits)
        self._auto_save_timer = None # For auto-saving text edits
        self._source_text_preview_timer = None # Initialize to None
        self._translated_text_preview_timer = None # Initialize to None
        self._scroll_sync_timer = None
        self.last_response = None # To store the last API response
        self._response_buffer = [] # Added response buffer

        # Initialize manager classes
        self.project_manager = ProjectManager(self)
        self.item_manager = ItemManager(self)
        self.preview_manager = PreviewManager(self)
        self.translation_manager = TranslationManager(self)
        self.token_manager = TokenManager(self)

        # Create a central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Create a layout for the central widget
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 10, 0) # Add right margin

        # Create a horizontal layout for the sidebar toggle and main splitter
        self.sidebar_and_content_layout = QHBoxLayout()
        self.sidebar_and_content_layout.setContentsMargins(0, 0, 0, 0) # Remove margins

        # Sidebar Toggle Button
        self.sidebar_toggle_button = QPushButton("«") # Using a simple character for now
        self.sidebar_toggle_button.setFixedSize(20, 20) # Make it small
        self.sidebar_toggle_button.clicked.connect(self.toggle_sidebar)
        self.sidebar_and_content_layout.addWidget(self.sidebar_toggle_button, alignment=Qt.AlignLeft | Qt.AlignTop) # Align top-left


        # Create the main horizontal splitter (sidebar + content)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.sidebar_and_content_layout.addWidget(self.main_splitter) # Add splitter to the new horizontal layout

        # Add the new horizontal layout to the main vertical layout
        self.main_layout.addLayout(self.sidebar_and_content_layout)


        # Create sidebar frame
        self.side_panel = QWidget(self.main_splitter)
        self.side_panel_layout = QVBoxLayout(self.side_panel)
        self.side_panel_layout.setContentsMargins(5, 5, 5, 5) # Add some padding

        # Sidebar Content
        self.item_label = QLabel("Project Items/Chapters")
        self.side_panel_layout.addWidget(self.item_label)

        self.item_listbox = QListWidget()
        self.side_panel_layout.addWidget(self.item_listbox)
        self.item_listbox.itemClicked.connect(self.item_selected)
        self.item_listbox.currentRowChanged.connect(self.on_item_selected) # Connect selection change
        self.item_listbox.itemChanged.connect(self._on_item_check_state_changed) # Connect item changed signal

        # Item Button Frame
        self.item_button_frame = QWidget()
        self.item_button_layout = QHBoxLayout(self.item_button_frame)
        self.item_button_layout.setContentsMargins(0, 0, 0, 0) # Remove margins

        self.add_item_button = QPushButton("Add")
        self.remove_item_button = QPushButton("Remove")
        self.rename_item_button = QPushButton("Rename")
        self.duplicate_item_button = QPushButton("Duplicate")

        self.item_button_layout.addWidget(self.add_item_button)
        self.item_button_layout.addWidget(self.remove_item_button)
        self.item_button_layout.addWidget(self.rename_item_button)
        self.item_button_layout.addWidget(self.duplicate_item_button)

        self.side_panel_layout.addWidget(self.item_button_frame)

        # Item Move Frame
        self.item_move_frame = QWidget()
        self.item_move_layout = QHBoxLayout(self.item_move_frame)
        self.item_move_layout.setContentsMargins(0, 0, 0, 0) # Remove margins

        self.move_item_up_button = QPushButton("Move Up")
        self.move_item_down_button = QPushButton("Move Down")

        self.item_move_layout.addWidget(self.move_item_up_button)
        self.item_move_layout.addWidget(self.move_item_down_button)

        self.side_panel_layout.addWidget(self.item_move_frame)

        self.calc_tokens_button = QPushButton("Calculate All Tokens")
        self.calc_tokens_button.clicked.connect(self.calculate_all_tokens)
        self.side_panel_layout.addWidget(self.calc_tokens_button)


        # Create main content area frame
        self.content_area = QWidget(self.main_splitter)
        self.content_area_layout = QVBoxLayout(self.content_area)
        self.content_area_layout.setContentsMargins(0, 0, 0, 0) # Remove margins
        # Placeholder for content area content


        # Create the editor/preview horizontal splitter
        self.editor_preview_splitter = QSplitter(Qt.Horizontal)
        self.content_area_layout.addWidget(self.editor_preview_splitter, 1) # Add splitter with stretch factor

        # Create editor frame
        self.editor_frame = QWidget(self.editor_preview_splitter)
        self.editor_frame_layout = QVBoxLayout(self.editor_frame)
        self.editor_frame_layout.setContentsMargins(0, 0, 0, 0) # Remove margins
        # Placeholder for editor content

        # Source Text Area
        self.source_label = QLabel("Source Text:")
        self.source_text_area = PlainTextEdit() # Use custom PlainTextEdit
        self.source_text_area.setObjectName("source_text_area") # Set object name
        self.source_text_area.setAcceptRichText(False) # Disable rich text (redundant but safe)
        self.editor_frame_layout.addWidget(self.source_label)
        self.editor_frame_layout.addWidget(self.source_text_area, 1) # Add source text area with stretch factor
        self.source_text_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Set size policy to expanding

        self.source_text_area.textChanged.connect(self.mark_dirty)
        self.source_text_area.textChanged.connect(self._schedule_auto_save) # Connected to new auto-save
        self.source_text_area.textChanged.connect(self._schedule_source_text_preview_update)
        self.source_text_area.cursorPositionChanged.connect(self._sync_source_scroll_to_preview)
        self.source_text_area.verticalScrollBar().valueChanged.connect(self._sync_source_scroll_to_preview)

        # Translated Text Area
        self.translated_label = QLabel("Translated Text:")
        self.translated_text_area = PlainTextEdit() # Use custom PlainTextEdit
        self.translated_text_area.setObjectName("translated_text_area") # Set object name
        self.translated_text_area.setAcceptRichText(False) # Disable rich text (redundant but safe)
        self.editor_frame_layout.addWidget(self.translated_label)
        self.editor_frame_layout.addWidget(self.translated_text_area, 1) # Add translated text area with stretch factor
        self.translated_text_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Set size policy to expanding

        # Initialize debounce timers before connecting signals
        self._debounce_timer = QTimer() # Kept for potential future use
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._update_token_counts) # Still connected, but not triggered by text edits

        self._auto_save_timer = QTimer() # New timer for auto-save
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._auto_save_and_update_current_item) # Connect to new method

        # Connect source text area signals
        # self.source_text_area.textChanged.connect(self.mark_dirty) # Already connected above
        # self.source_text_area.textChanged.connect(self._delayed_update_token_counts) # Disconnected above
        # self.source_text_area.textChanged.connect(self._schedule_auto_save) # Connected above
        # self.source_text_area.textChanged.connect(self._schedule_source_text_preview_update) # Already connected above
        # self.source_text_area.cursorPositionChanged.connect(self._sync_source_scroll_to_preview) # Already connected above
        # self.source_text_area.verticalScrollBar().valueChanged.connect(self._sync_source_scroll_to_preview) # Already connected above

        # Connect translated text area signals
        self.translated_text_area.textChanged.connect(self.mark_dirty)
        # self.translated_text_area.textChanged.connect(self._delayed_update_token_counts) # Disconnected
        self.translated_text_area.textChanged.connect(self._schedule_auto_save) # Connected to new auto-save
        self.translated_text_area.textChanged.connect(self._schedule_translated_text_preview_update)
        self.translated_text_area.cursorPositionChanged.connect(self._sync_target_scroll_to_preview)
        self.translated_text_area.verticalScrollBar().valueChanged.connect(self._sync_target_scroll_to_preview)


        # Create preview frame
        self.preview_frame = QWidget(self.editor_preview_splitter)
        self.preview_frame_layout = QVBoxLayout(self.preview_frame)
        self.preview_frame_layout.setContentsMargins(0, 0, 0, 0) # Remove margins
        # Placeholder for preview content

        # Source Text Preview
        self.source_text_preview_widget = QWidget()
        source_text_preview_layout = QVBoxLayout(self.source_text_preview_widget)
        source_text_preview_layout.setContentsMargins(0,0,0,0)
        source_text_preview_layout.addWidget(QLabel("Source Text Preview:"))
        if QWebEngineView and QWebEngineSettings:
            self.source_text_preview = QWebEngineView()
            self.source_text_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.source_text_preview.setHtml("<html><body><i>Preview unavailable</i></body></html>")
            # Explicitly enable JavaScript and set encoding
            self.source_text_preview.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            self.source_text_preview.settings().setDefaultTextEncoding("utf-8")
            source_text_preview_layout.addWidget(self.source_text_preview)
        else:
            source_text_preview_layout.addWidget(QLabel("QWebEngineView/QWebEngineSettings not available"))
        self.preview_frame_layout.addWidget(self.source_text_preview_widget)
        self.preview_frame_layout.addStretch(1) # Add stretch after source preview
        

        # Translated Text Preview
        self.translated_text_preview_widget = QWidget()
        translated_text_preview_layout = QVBoxLayout(self.translated_text_preview_widget)
        translated_text_preview_layout.setContentsMargins(0,0,0,0)
        translated_text_preview_layout.addWidget(QLabel("Translated Text Preview:"))
        if QWebEngineView and QWebEngineSettings:
            self.translated_text_preview = QWebEngineView()
            self.translated_text_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.translated_text_preview.setHtml("<html><body><i>Preview unavailable</i></body></html>")
            # Explicitly enable JavaScript and set encoding
            self.translated_text_preview.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            self.translated_text_preview.settings().setDefaultTextEncoding("utf-8")
            translated_text_preview_layout.addWidget(self.translated_text_preview)
        else:
            translated_text_preview_layout.addWidget(QLabel("QWebEngineView/QWebEngineSettings not available"))
        self.preview_frame_layout.addWidget(self.translated_text_preview_widget)
        self.preview_frame_layout.addStretch(1) # Add stretch after target preview


        # Add frames to the editor/preview splitter
        self.editor_preview_splitter.addWidget(self.editor_frame)
        self.editor_preview_splitter.addWidget(self.preview_frame)
        self.preview_frame.setVisible(False) # Hide preview on start


        # Add frames to the main splitter
        self.main_splitter.addWidget(self.side_panel)
        self.main_splitter.addWidget(self.content_area)

        # Bottom Control Frame
        self.bottom_control_frame = QWidget()
        self.bottom_control_layout = QHBoxLayout(self.bottom_control_frame) # Use QHBoxLayout for buttons
        self.bottom_control_layout.setContentsMargins(5, 5, 5, 5) # Add some padding

        # Bottom Control Buttons
        self.preview_request_button = QPushButton("Preview Request")
        self.preview_request_button.clicked.connect(self.show_request_payload) # Connect to show_request_payload
        self.translate_button = QPushButton("Translate ->")
        self.translate_button.clicked.connect(self.translate_current_item) # Connect to translate_current_item
        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.clicked.connect(self.stop_translation)
        self.stop_button.setEnabled(False)
        self.stop_button.setToolTip("Stop current translation")
        self.stop_button.setStyleSheet("""
            QPushButton {
                min-width: 80px;
                padding: 3px;
            }
            QPushButton:disabled {
                color: #888;
            }
        """)
        self.toggle_preview_button = QPushButton("Show Live Preview") # This button will toggle the preview panel
        self.toggle_preview_button.clicked.connect(self.toggle_live_preview_panel) # Connect to toggle_live_preview_panel

        # Add buttons to the layout
        self.bottom_control_layout.addWidget(self.preview_request_button)
        self.bottom_control_layout.addStretch(1) # Add stretch to push buttons to the right
        self.bottom_control_layout.addWidget(self.translate_button)
        self.bottom_control_layout.addWidget(self.stop_button) # Add stop button next to translate
        self.bottom_control_layout.addWidget(self.toggle_preview_button)

        self.content_area_layout.addWidget(self.bottom_control_frame)

        # Toolbar
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setAllowedAreas(Qt.ToolBarArea.NoToolBarArea) # Make toolbar not movable
        toolbar.toggleViewAction().setEnabled(False) # Make toolbar not disableable
        toolbar.setMovable(False) # Make toolbar non-detachable

        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        load_action = QAction("Load", self)
        load_action.setShortcut("Ctrl+O")
        self.save_action = QAction("Save", self)
        self.save_action.setShortcut("Ctrl+S")
        self.edit_action = QAction("Edit Project", self)
        self.edit_action.setShortcut("Ctrl+E")
        self.translate_action = QAction("Translate Item", self)
        self.translate_action.setShortcut("Ctrl+T")
        self.toggle_live_preview_action = QAction("Toggle Live Preview", self)
        self.toggle_live_preview_action.setCheckable(True)
        self.toggle_live_preview_action.setShortcut("Ctrl+Shift+M")
        self.view_request_action = QAction("View Request", self)
        self.view_request_action.setShortcut("Ctrl+R")
        self.view_response_action = QAction("Show Last Response", self)
        self.view_response_action.setShortcut("Ctrl+Shift+R")
        
        # Add About action
        self.about_action = QAction("About", self)
        self.about_action.setShortcut("F1")

        # Add Export as EPUB action
        self.export_epub_action = QAction("Export as EPUB", self)
        self.export_epub_action.setShortcut("Ctrl+Shift+E") # Choose an appropriate shortcut

        # Context mode selector
        self.context_mode_combo = QComboBox()
        modes = [
            ("Automatic (Fill Budget)", "Includes nearby items until token budget is nearly full"),
            ("Automatic (Strict Nearby)", "Includes exactly 2 items before and after current item"),
            ("Manual (Checkboxes)", "Manually select which items to include as context")
        ]

        for i, (text, tooltip) in enumerate(modes):
            self.context_mode_combo.addItem(text)
            self.context_mode_combo.setItemData(i, tooltip, Qt.ToolTipRole)

        current_mode = self.current_project_data.get("context_selection_mode", "fill_budget") if self.current_project_data else "fill_budget"
        initial_text = "Automatic (Fill Budget)"
        if current_mode == "manual":
            initial_text = "Manual (Checkboxes)"
        elif current_mode == "nearby":
            initial_text = "Automatic (Strict Nearby)"

        self.context_mode_combo.setCurrentText(initial_text)
        self.context_mode_combo.currentTextChanged.connect(self._on_context_mode_changed)
        self.context_mode_combo.setToolTip("Select how context items are chosen for translation")

        toolbar.addAction(new_action)
        toolbar.addAction(load_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.edit_action)
        toolbar.addAction(self.translate_action)
        toolbar.addAction(self.toggle_live_preview_action)
        toolbar.addAction(self.view_request_action)
        toolbar.addAction(self.view_response_action)
        toolbar.addSeparator()
        toolbar.addAction(self.about_action) # Add About action to toolbar
        toolbar.addAction(self.export_epub_action) # Add the new action to the toolbar
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Context Mode:"))
        toolbar.addWidget(self.context_mode_combo)


        # Connect Signals
        new_action.triggered.connect(self.new_project)
        load_action.triggered.connect(self.load_project)
        self.save_action.triggered.connect(self.save_project)
        self.edit_action.triggered.connect(self.edit_project_settings)
        self.translate_action.triggered.connect(self.translate_current_item)
        self.toggle_live_preview_action.triggered.connect(self.toggle_live_preview_panel)
        self.view_request_action.triggered.connect(self.show_request_payload)
        self.view_response_action.triggered.connect(self.show_last_response)
        self.about_action.triggered.connect(self.show_about)
        self.export_epub_action.triggered.connect(self.export_epub) # Connect the new action

        # Connect item buttons
        self.add_item_button.clicked.connect(self.add_item) # Keep one connection
        self.remove_item_button.clicked.connect(self.remove_item)
        self.rename_item_button.clicked.connect(self.rename_item)
        self.duplicate_item_button.clicked.connect(self.duplicate_item)
        self.move_item_up_button.clicked.connect(self.move_item_up)
        self.move_item_down_button.clicked.connect(self.move_item_down)

        # Status bar
        self.status = self.statusBar()
        self.status.showMessage("Ready")

        # Initial State
        self._update_ui_state()

    # --- EPUB Export ---
    def export_epub(self):
        """Handles the EPUB export process."""
        if not self.current_project_data:
            QMessageBox.warning(self, "Export EPUB", "No project loaded.")
            return

        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog # Uncomment if needed for debugging file dialog issues

        # Suggest a default filename based on project title
        default_filename = self.current_project_data.get('title', 'Exported_Project')
        default_filename = "".join(c for c in default_filename if c.isalnum() or c in (' ', '_', '-')).rstrip()
        default_filename = default_filename.replace(" ", "_") + ".epub"

        filepath, _ = QFileDialog.getSaveFileName(self, "Export Project as EPUB",
                                                  default_filename,
                                                  "EPUB Files (*.epub);;All Files (*)", options=options)

        if filepath:
            success, message = export_project_to_epub(self.current_project_data, filepath)
            if success:
                QMessageBox.information(self, "Export EPUB", f"Project successfully exported to:\n{filepath}")
            else:
                QMessageBox.critical(self, "Export EPUB Error", f"Failed to export EPUB:\n{message}")

    # --- Project Handling ---
    def new_project(self):
        self.project_manager.new_project()

    def load_project(self):
        self.project_manager.load_project()

    def load_project_data(self, project_title=None, project_filename=None):
        self.project_manager.load_project_data(project_title, project_filename)

    def save_project(self):
        self.project_manager.save_project()

    def edit_project_settings(self):
        self.project_manager.edit_project_settings()

    def mark_dirty(self):
        if not self.is_dirty and self.current_project_data:
            self.is_dirty = True
            self._update_ui_state()

    def closeEvent(self, event):
        if self._check_unsaved_changes():
            # Clean up temporary preview file
            if hasattr(self, '_temp_preview_file') and self._temp_preview_file and os.path.exists(self._temp_preview_file):
                try:
                    os.remove(self._temp_preview_file)
                except Exception as cleanup_e:
                    pass
            event.accept()
        else:
            event.ignore()

    def _check_unsaved_changes(self):
        if self.is_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Do you want to save them before closing?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                         QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                self.save_project()
                return not self.is_dirty # Return True if save was successful (is_dirty becomes False)
            elif reply == QMessageBox.Discard:
                return True # Proceed with closing
            else:
                return False # Cancel closing
        return True # No unsaved changes, proceed with closing

    # --- Item Manipulation Methods ---
    def _refresh_listbox_display(self):
        self.item_listbox.blockSignals(True)
        self.item_listbox.clear()
        current_selection_row = self.current_item_index
        included_indices, excluded_indices = self._get_context_item_indices()

        for i, item in enumerate(self.project_items):
            name = item.get("name", f"Item {i+1}")
            source_tokens = self.count_tokens(item.get('source_text', ''))
            target_tokens = self.count_tokens(item.get('translated_text', ''))
            display_text = f"{i + 1}. {name.ljust(40)} S:{source_tokens:4} T:{target_tokens:4}"

            list_item = QListWidgetItem(display_text)

            # Add checkbox if in manual context mode
            if self.current_project_data and self.current_project_data.get("context_selection_mode") == "manual":
                 list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
                 # Set initial checked state based on item data, default to checked if key doesn't exist
                 is_checked = item.get("include_in_context", True)
                 list_item.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)
            else:  
                 # Ensure no checkbox if not in manual mode
                 list_item.setFlags(list_item.flags() & ~Qt.ItemIsUserCheckable)
                 list_item.setCheckState(Qt.Unchecked) # Clear check state

            if i == self.current_item_index:
                list_item.setBackground(QColor(255, 165, 0))
            elif i in included_indices:
                list_item.setBackground(QColor(144, 238, 144))
            elif i in excluded_indices:
                list_item.setBackground(Qt.lightGray)
            else:
                list_item.setBackground(Qt.white)

            self.item_listbox.addItem(list_item)

        if current_selection_row is not None and 0 <= current_selection_row < self.item_listbox.count():
            self.item_listbox.setCurrentRow(current_selection_row)
        else:
             self.current_item_index = None
             self.source_text_area.clear()
             self.translated_text_area.clear()

        self.item_listbox.blockSignals(False)
        self._update_ui_state()

    def _update_listbox_item_display(self, index):
        if 0 <= index < len(self.project_items) and 0 <= index < self.item_listbox.count():
            item_data = self.project_items[index]
            name = item_data.get("name", f"Item {index + 1}")
            source_tokens = self.count_tokens(item_data.get('source_text', ''))
            target_tokens = self.count_tokens(item_data.get('translated_text', ''))
            display_text = f"{index + 1}. {name.ljust(40)} S:{source_tokens:4} T:{target_tokens:4}"
            list_item = self.item_listbox.item(index)
            if list_item:
                list_item.setText(display_text)
                included_indices, excluded_indices = self._get_context_item_indices()
                if index == self.current_item_index:
                    list_item.setBackground(Qt.cyan)
                elif index in included_indices:
                    list_item.setBackground(Qt.green)
                elif index in excluded_indices:
                    list_item.setBackground(Qt.lightGray)
                else:
                    list_item.setBackground(Qt.white)

    def add_item(self):
        self.item_manager.add_item()

    def remove_item(self):
        self.item_manager.remove_item()

    def rename_item(self):
        self.item_manager.rename_item()

    def duplicate_item(self):
        self.item_manager.duplicate_item()

    def move_item_up(self):
        self.item_manager.move_item_up()

    def move_item_down(self):
        self.item_manager.move_item_down()

    def update_move_button_states(self):
        list_count = self.item_listbox.count()
        can_move_up = self.current_item_index is not None and self.current_item_index > 0
        can_move_down = self.current_item_index is not None and self.current_item_index < list_count - 1

        self.move_item_up_button.setEnabled(can_move_up)
        self.move_item_down_button.setEnabled(can_move_down)

    def toggle_sidebar(self):
        if self.side_panel.isVisible():
            self.side_panel.hide()
            self.sidebar_toggle_button.setText("»")
        else:
            self.side_panel.show()
            self.sidebar_toggle_button.setText("«")

    def item_selected(self, item):
        pass

    def _on_context_mode_changed(self, mode_text):
        if not self.current_project_data:
            return

        mode_mapping = {
            "Manual (Checkboxes)": "manual",
            "Automatic (Strict Nearby)": "nearby",
            "Automatic (Fill Budget)": "fill_budget"
        }

        new_mode = mode_mapping.get(mode_text, "fill_budget")
        current_mode = self.current_project_data.get("context_selection_mode", "fill_budget")

        if new_mode != current_mode:
            self.current_project_data["context_selection_mode"] = new_mode
            self.mark_dirty()
            self._refresh_listbox_display()
            self._update_ui_state()

    def _save_text_for_index(self, index_to_save):
        """Saves the current text area content to the specified project item index."""
        if index_to_save is None or not self.current_project_data or not (0 <= index_to_save < len(self.project_items)):
            # print(f"DEBUG: Skipping save for index {index_to_save} - invalid index or no project.")
            return # Don't proceed if index is invalid or no project

        try:
            item = self.project_items[index_to_save]
            current_source = self.source_text_area.toPlainText()
            current_target = self.translated_text_area.toPlainText()

            # Always save the text, don't check if it changed
            item['source_text'] = current_source
            item['translated_text'] = current_target
            self._clear_token_cache() # Clear cache as text content might have changed token count even if text looks same
            self.mark_dirty() # Mark dirty as data was potentially updated
            # print(f"DEBUG: Saved text for index {index_to_save}")

            # Note: We don't call _update_token_counts or _update_listbox_item_display here.
            # The caller (on_item_selected or the auto-save timer) is responsible for UI updates.

        except IndexError:
             print(f"Warning: Could not save text for item index {index_to_save}, index out of range.")
        except Exception as e:
             print(f"Warning: Error saving text for index {index_to_save}: {e}")

    def _get_context_item_indices(self):
        if self.current_item_index is None or not self.current_project_data:
            return set(), set()

        mode = self.current_project_data.get("context_selection_mode", "fill_budget")

        if mode == "manual":
            included = set()
            excluded = set()
            for i in range(self.item_listbox.count()):
                list_item = self.item_listbox.item(i)
                if list_item.checkState() == Qt.Checked:
                    included.add(i)
                else:
                    excluded.add(i)
            return included, excluded

        elif mode == "fill_budget":
            context_limit = self.current_project_data.get('context_token_limit_approx', -1)
            if context_limit <= 0:
                return set(), set()

            included = set()
            excluded = set()
            current_token_count = 0
            target_token_budget = int(context_limit * 0.8)

            left, right = self.current_item_index - 1, self.current_item_index + 1
            while left >= 0 or right < len(self.project_items):
                if left >= 0:
                    item = self.project_items[left]
                    item_tokens = self.count_tokens(item.get('source_text', '')) + \
                                 self.count_tokens(item.get('translated_text', ''))

                    if current_token_count + item_tokens <= target_token_budget:
                        included.add(left)
                        current_token_count += item_tokens
                    else:
                        excluded.add(left)
                    left -= 1

                if right < len(self.project_items):
                    item = self.project_items[right]
                    item_tokens = self.count_tokens(item.get('source_text', '')) + \
                                 self.count_tokens(item.get('translated_text', ''))

                    if current_token_count + item_tokens <= target_token_budget:
                        included.add(right)
                        current_token_count += item_tokens
                    else:
                        excluded.add(right)
                    right += 1
            return included, excluded
        elif mode == "nearby":
            context_limit = self.current_project_data.get('context_token_limit_approx', -1)

            included = {self.current_item_index}
            excluded = set()

            if context_limit <= 0:
                for i in range(len(self.project_items)):
                    if i != self.current_item_index:
                        excluded.add(i)
                return included, excluded

            current_token_count = 0
            target_token_budget = context_limit

            left = self.current_item_index - 1
            right = self.current_item_index + 1

            while (left >= 0 or right < len(self.project_items)):
                added_in_iteration = False

                if right < len(self.project_items):
                    item = self.project_items[right]
                    item_tokens = self.count_tokens(item.get('source_text', '')) + \
                                 self.count_tokens(item.get('translated_text', ''))

                    if current_token_count + item_tokens <= target_token_budget:
                        included.add(right)
                        current_token_count += item_tokens
                        added_in_iteration = True
                    else:
                        pass
                    right += 1

                if left >= 0:
                    item = self.project_items[left]
                    item_tokens = self.count_tokens(item.get('source_text', '')) + \
                                 self.count_tokens(item.get('translated_text', ''))

                    if current_token_count + item_tokens <= target_token_budget:
                        included.add(left)
                        current_token_count += item_tokens
                        added_in_iteration = True
                    else:
                        pass
                    left -= 1

                if not added_in_iteration and (left < 0 and right >= len(self.project_items)):
                    break
                elif not added_in_iteration:
                    break

            for i in range(len(self.project_items)):
                if i not in included:
                    excluded.add(i)

            return included, excluded

        return set(), set()

    def _delayed_update_token_counts(self):
        if not hasattr(self, '_debounce_timer'):
            self._debounce_timer = QTimer()
            self._debounce_timer.setSingleShot(True)
            self._debounce_timer.timeout.connect(self._update_token_counts)

        self._debounce_timer.start(500)

    def _update_token_counts(self):
        if not self.current_project_data or getattr(self, '_updating_token_counts', False):
            return

        try:
            self._updating_token_counts = True
            self.source_text_area.blockSignals(True)
            self.translated_text_area.blockSignals(True)
            self.item_listbox.blockSignals(True)
            if not hasattr(self, 'item_listbox'):
                return
            for i in range(len(self.project_items)):
                item = self.project_items[i]
                source_tokens = self.count_tokens(item.get('source_text', ''))
                target_tokens = self.count_tokens(item.get('translated_text', ''))
 
                if i < self.item_listbox.count():
                    list_item = self.item_listbox.item(i)
                    item_number = i + 1 # Define item_number explicitly
                    display_text = f"{item_number}. {item.get('name', 'Item').ljust(40)} S:{source_tokens:4} T:{target_tokens:4}"
                    list_item.setText(display_text)
 
            if self.current_item_index is not None:
                self._save_text_for_index(self.current_item_index)




        except Exception as e:
            print(f"Warning: Could not update token counts: {e}")
        finally:
            self._updating_token_counts = False
            # Ensure signals are unblocked even if there was an error
            if hasattr(self, 'source_text_area'): self.source_text_area.blockSignals(False)
            if hasattr(self, 'translated_text_area'): self.translated_text_area.blockSignals(False)
            if hasattr(self, 'item_listbox'): self.item_listbox.blockSignals(False)


    def on_item_selected(self, current_row):
        # Store the index of the item *before* changing selection
        previous_item_index = self.current_item_index

        # Explicitly save the text for the *previous* item if the selection changed
        if previous_item_index is not None and previous_item_index != current_row:
             # print(f"DEBUG: Item selection changed from {previous_item_index} to {current_row}. Saving previous item.")
             self._save_text_for_index(previous_item_index) # Use the renamed function

        # Update the current index *after* potentially saving the previous one
        self.current_item_index = current_row
        # print(f"DEBUG: Current item index set to {self.current_item_index}")

        # Load the new item's data into text areas
        if self.current_item_index >= 0 and self.current_project_data:
            try:
                item_data = self.project_items[self.current_item_index]
                self.source_text_area.blockSignals(True)
                self.translated_text_area.blockSignals(True)
                self.source_text_area.setPlainText(item_data.get('source_text', ''))
                self.translated_text_area.setPlainText(item_data.get('translated_text', ''))
                self.source_text_area.blockSignals(False)
                self.translated_text_area.blockSignals(False)
            except IndexError:
                QMessageBox.critical(self, "Error", f"Selected item index {self.current_item_index} is out of range.")
                self.current_item_index = None
                self.source_text_area.clear()
                self.translated_text_area.clear()
            except Exception as e:
                 QMessageBox.critical(self, "Error", f"Failed to load item data: {e}")
                 self.current_item_index = None
                 self.source_text_area.clear()
                 self.translated_text_area.clear()
        else:
            self.source_text_area.clear()
            self.translated_text_area.clear()

        self._refresh_listbox_display()
        self._update_ui_state()

    def _on_item_check_state_changed(self, item):
        """Handles the check state change of an item in the listbox."""
        row = self.item_listbox.row(item)
        if 0 <= row < len(self.project_items) and self.current_project_data and self.current_project_data.get("context_selection_mode") == "manual":
            is_checked = item.checkState() == Qt.Checked
            self.project_items[row]["include_in_context"] = is_checked
            self.mark_dirty()
            # Re-calculate and update status bar to reflect context change
            self._update_ui_state()

    # --- Auto-Save and Token Update ---
    def _schedule_auto_save(self):
        """Schedules the auto-save and current item update."""
        if not hasattr(self, '_auto_save_timer'):
            self._auto_save_timer = QTimer()
            self._auto_save_timer.setSingleShot(True)
            self._auto_save_timer.timeout.connect(self._auto_save_and_update_current_item)
        self._auto_save_timer.start(500) # 500ms delay

    def _auto_save_and_update_current_item(self):
        """Saves the current item's text and updates its display in the listbox."""
        if self.current_item_index is None or not self.current_project_data:
            return

        try:
            # Save text from editors to the in-memory project data using the current index
            self._save_text_for_index(self.current_item_index) # Use the renamed function
            # Update the display (including tokens) for the current item in the listbox
            self._update_listbox_item_display(self.current_item_index)
        except Exception as e:
            print(f"Warning: Error during auto-save or item update: {e}")

    # --- Live Markdown Preview ---
    def toggle_live_preview_panel(self):
        self.preview_manager.toggle_live_preview_panel()

    def _sync_source_scroll_to_preview(self):
        self.preview_manager._sync_source_scroll_to_preview()

    def _sync_target_scroll_to_preview(self):
        self.preview_manager._sync_target_scroll_to_preview()

    def _schedule_source_text_preview_update(self):
        self.preview_manager._schedule_source_text_preview_update()

    def _schedule_translated_text_preview_update(self):
        self.preview_manager._schedule_translated_text_preview_update()

    # --- Request/Response Display Methods ---
    def show_request_payload(self):
        if self.current_item_index is None or not self.current_project_data:
            QMessageBox.warning(self, "View Request", "No item selected or project loaded.")
            return

        payload = self._build_api_payload()
        if not payload:
            return

        try:
            dialog = QDialog(self)
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
            QMessageBox.critical(self, "Error", f"Failed to show request payload:\n{e}")

    def show_last_response(self):
        if not hasattr(self, 'last_response') or self.last_response is None:
            QMessageBox.information(self, "Last Response", "No response has been received yet.")
            return

        try:
            dialog = QDialog(self)
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
                response_data = json.loads(self.last_response)
                formatted_edit.setPlainText(json.dumps(response_data, indent=4, ensure_ascii=False))
            except json.JSONDecodeError:
                formatted_edit.setPlainText(str(self.last_response))
            formatted_layout.addWidget(formatted_edit)
            tab_widget.addTab(formatted_tab, "Formatted")

            raw_tab = QWidget()
            raw_layout = QVBoxLayout(raw_tab)
            raw_label = QLabel("Raw Text Response:")
            raw_layout.addWidget(raw_label)

            raw_edit = QTextEdit()
            raw_edit.setReadOnly(True)
            raw_edit.setPlainText(str(self.last_response))
            raw_layout.addWidget(raw_edit)
            tab_widget.addTab(raw_tab, "Raw Text")

            layout.addWidget(tab_widget)

            button_box = QDialogButtonBox(QDialogButtonBox.Close)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to show response:\n{e}")

    # --- Translation ---
    def _build_api_payload(self):
        if self.current_item_index is None or not self.current_project_data:
            QMessageBox.warning(self, "Translation", "No item selected or project loaded.")
            return None

        source_text = self.source_text_area.toPlainText().strip()
        target_language = self.current_project_data.get('target_language', '')
        model_name = self.current_project_data.get('model', '')
        context_limit = self.current_project_data.get('context_token_limit_approx', -1)
        prompt_config = self.current_project_data.get('prompt_config', {})

        if not all([source_text, target_language, model_name]):
            QMessageBox.warning(self, "Translation",
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
        included_indices, _ = self._get_context_item_indices()
        context_token_count = 0

        context_indices_to_use = sorted([idx for idx in included_indices if idx != self.current_item_index])

        for i in context_indices_to_use:
            try:
                item = self.project_items[i]
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
                    context_token_count += self.count_tokens(item_source) + self.count_tokens(item_translation)

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

    def _build_api_payload(self):
        return self.translation_manager._build_api_payload()


    def count_tokens(self, text: str) -> int:
        return self.token_manager.count_tokens(text)

    def _clear_token_cache(self):
        self.token_manager._clear_token_cache()

    def calculate_all_tokens(self):
        self.token_manager.calculate_all_tokens()

    def translate_current_item(self):
        self.translation_manager.translate_current_item()

    def stop_translation(self):
        self.translation_manager.stop_translation()

    def _handle_translation_chunk(self, chunk):
        self.translation_manager._handle_translation_chunk(chunk)

    def _handle_translation_finished(self):
        self.translation_manager._handle_translation_finished()

    def _handle_translation_error(self, error_msg):
        self.translation_manager._handle_translation_error(error_msg)



    def preview_request(self):
        pass

    def _update_ui_state(self):
        project_loaded = self.current_project_data is not None
        item_selected = self.current_item_index is not None

        self.save_action.setEnabled(project_loaded)
        self.edit_action.setEnabled(project_loaded)
        self.translate_action.setEnabled(project_loaded and item_selected)
        self.toggle_live_preview_action.setEnabled(project_loaded and QWebEngineView is not None)
        self.export_epub_action.setEnabled(project_loaded) # Enable export action when project is loaded

        self.add_item_button.setEnabled(project_loaded)
        self.remove_item_button.setEnabled(project_loaded and item_selected)
        self.rename_item_button.setEnabled(project_loaded and item_selected)
        self.duplicate_item_button.setEnabled(project_loaded and item_selected)

        if project_loaded:
            self.update_move_button_states()
        else:
            self.move_item_up_button.setEnabled(False)
            self.move_item_down_button.setEnabled(False)

        self.source_text_area.setEnabled(project_loaded and item_selected)
        self.translated_text_area.setEnabled(project_loaded and item_selected)

        if project_loaded and self.is_dirty:
            self.save_action.setText("Save*")
        elif project_loaded:
             self.save_action.setText("Save")

        if project_loaded:
            if item_selected:
                included, excluded = self._get_context_item_indices()
                context_limit = self.current_project_data.get('context_token_limit_approx', -1)
                mode = self.current_project_data.get("context_selection_mode", "fill_budget")
                mode_display = {
                    "fill_budget": "Automatic (Fill Budget)",
                    "nearby": "Automatic (Strict Nearby)",
                    "manual": "Manual (Checkboxes)"
                }.get(mode, "Unknown")

                current_token_count = 0
                context_item_indices = set(idx for idx in included if idx != self.current_item_index)

                for i in context_item_indices:
                    try:
                        item = self.project_items[i]
                        current_token_count += self.count_tokens(item.get('source_text', ''))
                        current_token_count += self.count_tokens(item.get('translated_text', ''))
                    except IndexError:
                        print(f"Warning: Index {i} out of range during status bar update.")

                if context_limit > 0:
                    status_msg = (f"Mode: {mode_display} | Context: {len(context_item_indices)} items ({current_token_count}/{context_limit} tokens) | "
                                  f"Excluded: {len(excluded)} items")
                    if current_token_count > context_limit:
                        status_msg += " [WARNING: Over budget]"
                else:
                    status_msg = f"Mode: {mode_display} | Context: {len(context_item_indices)} items (Unlimited tokens) | Excluded: {len(excluded)} items"

                self.statusBar().showMessage(status_msg)
            else:
                project_title = self.current_project_data.get("title", "Untitled Project")
                self.statusBar().showMessage(f"Project '{project_title}' loaded. Select an item or add a new one.")
        else:
            self.statusBar().showMessage(f"SagaTrans v{self.VERSION} - No project loaded. Use 'New' or 'Load' from the toolbar.")

    # --- About Dialog ---
    def show_about(self):
        """Display the About dialog with program information."""
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle(f"About SagaTrans v{self.VERSION}")
        about_dialog.setFixedSize(400, 300)
        about_dialog.setModal(True)
        
        layout = QVBoxLayout(about_dialog)
        
        # Create a title label with icon
        title_label = QLabel("SagaTrans")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px;")
        layout.addWidget(title_label)
        
        # Version label
        version_label = QLabel(f"Version {self.VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # Description
        description_label = QLabel(
            "SagaTrans is a translation tool for novels and stories.\n\n"
            "Features:\n"
            "• AI-powered translation using various models\n"
            "• Context-aware translation with project-wide context\n"
            "• Live preview of translations\n"
            "• Export to EPUB format\n"
            "• Token counting and management\n\n"
            "Built with PyQt5 and designed for translators and novel enthusiasts."
        )
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(description_label)
        
        # Copyright
        copyright_label = QLabel("© 2025 Pierun0")
        copyright_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_label)
        
        # GitHub link
        github_label = QLabel("GitHub: https://github.com/Pierun0/SagaTrans")
        github_label.setAlignment(Qt.AlignCenter)
        github_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        github_label.setOpenExternalLinks(True)
        layout.addWidget(github_label)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(about_dialog.accept)
        layout.addWidget(button_box)
        
        about_dialog.exec_()

