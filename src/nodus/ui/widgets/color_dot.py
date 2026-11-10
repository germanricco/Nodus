"""A filled circle in a color the user chose: a category's, a tag's or a series'."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


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
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(self.rect())
        painter.end()
