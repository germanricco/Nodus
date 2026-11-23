"""A boxed caption and figure, for rows of totals."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space


class FigureTile(QFrame):
    """A boxed caption and value, like the Income / Expenses / Saved boxes of the reference,
    optionally with a ``badge`` under the value (e.g. a ``ChangeBadge``).

    Every tile has the same size of figure, so a row of tiles reads as peers; the figure a
    page is about goes above them, in a ``HeroFigure`` (plan 029a, 5.2).
    """

    def __init__(self, caption: str, value: QLabel, badge: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("FigureTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.M, Space.S, Space.M, Space.S)
        layout.setSpacing(Space.XXS)
        # Tiles in a row share their height; the figures stay on top, lined up.
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        caption_label = QLabel(caption.upper())
        caption_label.setObjectName("StatCaption")
        value.setObjectName("StatValue")
        value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.value = value
        layout.addWidget(caption_label)
        layout.addWidget(value)
        if badge is not None:
            layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)
