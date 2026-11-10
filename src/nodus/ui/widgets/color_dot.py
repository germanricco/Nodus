"""A filled circle in a color the user chose: a category's, a tag's or a series'."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from nodus.ui.theme.contrast import outline_for
from nodus.ui.theme.design import Line
from nodus.ui.theme.theme_manager import active_theme


def paint_dot(painter: QPainter, rect: QRectF, color: str) -> None:
    """A circle in ``color`` filling ``rect``, ringed in a deeper shade of itself when
    the color alone would fade into the theme's surface (a yellow on white), so every
    dot reads as a shape without changing the color the user chose."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(rect)
    outline = outline_for(color, active_theme().surface)
    if outline is not None:
        half = Line.THIN / 2  # the ring's stroke stays inside the circle
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(outline), Line.THIN))
        painter.drawEllipse(rect.adjusted(half, half, -half, -half))


class ColorDot(QWidget):
    """A small filled circle in a category's color, painted rather than styled, so the
    user's color never becomes part of a stylesheet. Without a color it is empty."""

    def __init__(self, color: str = "", size: int = 12, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(size, size)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        if not self._color:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_dot(painter, QRectF(self.rect()), self._color)
        painter.end()
