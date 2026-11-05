"""Base class for the main sections."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class Page(QWidget):
    """A main section: a title and a content area that subclasses fill.

    ``refresh`` runs every time the page is shown, so it always reflects current data.
    """

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(16)
        layout.addLayout(self.content_layout, stretch=1)

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
