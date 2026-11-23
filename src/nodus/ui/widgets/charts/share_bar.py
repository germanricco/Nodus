"""A thin bar filled to an item's share of a total, in the item's color."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from nodus.ui.theme.design import ControlSize
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.charts.budget_bar import paint_progress
from nodus.ui.widgets.charts.chart_base import ProgressStrip


class ShareBar(ProgressStrip):
    """How much of its kind a category weighs, so the bars of a list compare at a glance:
    the same track as a budget's or a goal's, filled in the category's color."""

    HEIGHT = ControlSize.PROGRESS_HEIGHT

    def __init__(
        self,
        theme: Theme,
        share: float,
        color: str,
        start: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(theme, self.HEIGHT, start, parent)
        self.share = share
        self.color = color
        self._begin()

    @property
    def fraction(self) -> float:
        return self.share

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        paint_progress(
            painter,
            QRectF(0, 0, self.width(), self.HEIGHT),
            self.shown_fraction,
            self.color,
            self._theme.border,
        )
        painter.end()
