"""Main application window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow

from nodus import __version__


class MainWindow(QMainWindow):
    """Top-level window. For now it only shows a placeholder; the sidebar and pages come next."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nodus")
        self.resize(1280, 800)
        placeholder = QLabel(f"Nodus {__version__}")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
