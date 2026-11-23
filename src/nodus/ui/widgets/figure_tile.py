"""A boxed caption and figure, for rows of totals."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space


class FigureTile(QFrame):
    """A boxed caption and value, like the Income / Expenses / Saved boxes of the reference,
    optionally with a ``badge`` (e.g. a ``ChangeBadge``).

    The badge goes under the value, or beside it with ``badge_beside``: in a row where only
    one tile has a badge, beside keeps that tile as short as the others, which would
    otherwise share its extra height as empty room. The tile asks for the width of both,
    so a ``FigureRow`` wraps it instead of cutting either.

    Every tile has the same size of figure, so a row of tiles reads as peers; the figure a
    page is about goes above them, in a ``HeroFigure`` (plan 029a, 5.2).
    """

    def __init__(
        self,
        caption: str,
        value: QLabel,
        badge: QWidget | None = None,
        badge_beside: bool = False,
    ) -> None:
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
        if badge is not None and badge_beside:
            line = QHBoxLayout()
            line.setSpacing(Space.S)
            line.addWidget(value)
            line.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
            line.addStretch()
            layout.addLayout(line)
            return
        layout.addWidget(value)
        if badge is not None:
            layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)
