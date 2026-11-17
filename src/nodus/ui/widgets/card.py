"""Rounded panel that groups related content."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space


class Card(QFrame):
    """A surface with a border and rounded corners, optionally titled.

    Content goes into ``body``, a vertical layout.
    """

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(Space.XL, Space.L, Space.XL, Space.L)
        self.body.setSpacing(Space.S)
        if title:
            self.body.addWidget(card_title(title))


def card_title(title: str) -> QLabel:
    """A card's title, in small capitals like every other."""
    label = QLabel(title.upper())
    label.setObjectName("CardTitle")
    return label


def card_header(card: Card, title: str) -> QHBoxLayout:
    """A title on the left with room on the right, e.g. for a ``ChangeBadge``."""
    header = QHBoxLayout()
    header.setSpacing(Space.S)
    header.addWidget(card_title(title))
    header.addStretch()
    card.body.addLayout(header)
    return header


def see_all_link(header: QHBoxLayout, text: str, slot: Callable[[], object]) -> QPushButton:
    """A small link at the right of a card's header to the page with the whole list, in
    the same place on every card and without taking a row of its own."""
    button = QPushButton(f"{text} ›")
    button.setObjectName("LinkButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(slot)
    header.addWidget(button)
    return button
