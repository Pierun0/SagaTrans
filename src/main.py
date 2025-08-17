import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QAction, QSplitter, QWidget, QVBoxLayout, QToolBar,
    QFileDialog, QMessageBox, QListWidget, QPushButton, QHBoxLayout, QInputDialog, QDialog, QLineEdit, QDialogButtonBox, QLabel,
    QListWidgetItem, QTabWidget, QComboBox, QSizePolicy
)
from model_manager import ModelManager
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QUrl
from PyQt5.QtGui import QColor

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError as e:
    print(f"Failed to import QWebEngineView: {e}")
    QWebEngineView = None
import os
from ui.qt_main_window import QtMainWindow # Import the new QtMainWindow

# Set environment variable for QWebEngineView
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox"

    # --- Main Execution ---
def main():
    # Set AppUserModelID for proper taskbar icon on Windows
    try:
        from PyQt5.QtWinExtras import QtWin
        myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
        QtWin.setCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass # Not on Windows or QtWinExtras not available

    app = QApplication(sys.argv)

    # --- Explicitly initialize WebEngine ---
    if QWebEngineView:
        try:
            # Note: QWebEngineView doesn't have a direct initialize method.
            # Initialization happens implicitly when the first view is created
            # or potentially via QWebEngineProfile.defaultProfile().
            # Let's try accessing the default profile to potentially trigger initialization.
            from PyQt5.QtWebEngineWidgets import QWebEngineProfile
            profile = QWebEngineProfile.defaultProfile()
        except Exception as e:
            pass
        else:
            pass

    # Apply a style? e.g., app.setStyle('Fusion')
    model_manager = ModelManager()
    window = QtMainWindow(model_manager) # Use the new QtMainWindow with model manager
    
    # Show main window directly without initial project selection
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
