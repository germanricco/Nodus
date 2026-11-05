"""Rounded panel that groups related content."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    """A surface with a border and rounded corners, optionally titled.

    Content goes into ``body``, a vertical layout.
    """

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 16, 20, 16)
        self.body.setSpacing(8)
        if title:
            title_label = QLabel(title.upper())
            title_label.setObjectName("CardTitle")
            self.body.addWidget(title_label)
