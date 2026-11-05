"""Base class for the main sections."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class Page(QWidget):
    """A main section: a title and a content area that subclasses fill.

    ``refresh`` runs every time the page is shown, so it always reflects current data.
    """

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)
        self._header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        self._header.addWidget(title_label)
        self._header.addStretch()
        layout.addLayout(self._header)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(16)
        layout.addLayout(self.content_layout, stretch=1)

    def add_header_button(self, text: str, primary: bool = False) -> QPushButton:
        """Adds a button to the right of the title, for the page's main actions."""
        button = QPushButton(text)
        button.setObjectName("PrimaryButton" if primary else "SecondaryButton")
        self._header.addWidget(button)
        return button

    def refresh(self) -> None:
        """Reloads the page's data. Pages that show stored data override it."""


class PlaceholderPage(Page):
    """Stand-in for a section whose screen is not built yet."""

    def __init__(self, title: str) -> None:
        super().__init__(title)
        message = QLabel("Esta sección se está construyendo.")
        message.setObjectName("EmptyState")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(message, stretch=1)
