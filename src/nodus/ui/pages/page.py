"""Base class for the main sections."""

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
        self.add_header_widget(button)
        return button

    def add_header_widget(self, widget: QWidget) -> None:
        """Adds a control to the right of the title, e.g. a month selector."""
        self._header.addWidget(widget)

    def refresh(self) -> None:
        """Reloads the page's data. Pages that show stored data override it."""
