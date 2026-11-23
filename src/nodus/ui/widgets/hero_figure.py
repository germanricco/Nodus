"""The figure a page is about, large and without a box, above the boxes of the rest."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space


class HeroFigure(QWidget):
    """The answer to a page's question (an account's balance, what a goal has saved): its
    caption, the value in ``DISPLAY`` and an optional ``note`` under it.

    It stands alone, like the net worth, so the boxes of the other figures stay all the
    same size (plan 029a, 5.2). A page has at most one.
    """

    def __init__(self, caption: str, value: QLabel, note: QWidget | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.XXS)
        caption_label = QLabel(caption.upper())
        caption_label.setObjectName("StatCaption")
        value.setObjectName("StatValueHero")
        value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.value = value
        layout.addWidget(caption_label)
        layout.addWidget(value)
        if note is not None:
            layout.addWidget(note, alignment=Qt.AlignmentFlag.AlignLeft)
