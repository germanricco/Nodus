"""Small charts painted directly, so they follow the theme without extra libraries."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from nodus.ui.theme.theme import Theme


@dataclass(frozen=True)
class Segment:
    """A slice of a chart: its color and its size (any unit, only proportions matter)."""

    color: str
    value: int


class DonutChart(QWidget):
    """A ring split by segment size, with a caption and a figure in the middle."""

    THICKNESS = 26
    GAP_DEGREES = 1.5

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._segments: list[Segment] = []
        self._caption = ""
        self._text = ""
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, segments: list[Segment], caption: str, text: str) -> None:
        self._segments = [s for s in segments if s.value > 0]
        self._caption = caption
        self._text = text
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(220, 220)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) - self.THICKNESS
        ring = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        self._paint_ring(painter, ring)
        self._paint_center(painter, ring)
        painter.end()

    def _paint_ring(self, painter: QPainter, ring: QRectF) -> None:
        total = sum(s.value for s in self._segments)
        if total == 0:
            painter.setPen(self._pen(self._theme.border))
            painter.drawEllipse(ring)
            return
        gap = self.GAP_DEGREES if len(self._segments) > 1 else 0
        start = 90.0  # 12 o'clock, going clockwise
        for segment in self._segments:
            span = 360.0 * segment.value / total
            painter.setPen(self._pen(segment.color))
            # Qt angles are in 1/16 degree and run counterclockwise.
            painter.drawArc(ring, int((start - gap / 2) * 16), int(-(span - gap) * 16))
            start -= span

    def _paint_center(self, painter: QPainter, ring: QRectF) -> None:
        caption_font = QFont(self.font())
        caption_font.setPointSizeF(self.font().pointSizeF() * 0.9)
        value_font = QFont(self.font())
        value_font.setPointSizeF(self.font().pointSizeF() * 1.35)
        value_font.setWeight(QFont.Weight.DemiBold)
        middle = ring.center().y()
        painter.setPen(QColor(self._theme.text_muted))
        painter.setFont(caption_font)
        painter.drawText(
            QRectF(ring.left(), middle - 26, ring.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            self._caption,
        )
        painter.setPen(QColor(self._theme.text))
        painter.setFont(value_font)
        painter.drawText(
            QRectF(ring.left(), middle - 4, ring.width(), 28),
            Qt.AlignmentFlag.AlignCenter,
            self._text,
        )

    def _pen(self, color: str) -> QPen:
        pen = QPen(QColor(color), self.THICKNESS)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        return pen


class ProportionBar(QWidget):
    """A thin horizontal bar split between segments, e.g. income against expenses."""

    HEIGHT = 10

    def __init__(self, theme: Theme, segments: list[Segment], parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self._segments = [s for s in segments if s.value > 0]
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self.HEIGHT / 2
        total = sum(s.value for s in self._segments)
        if total == 0:
            painter.setBrush(QColor(self._theme.border))
            painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
            painter.end()
            return
        left = 0.0
        gap = 3 if len(self._segments) > 1 else 0
        for index, segment in enumerate(self._segments):
            width = self.width() * segment.value / total
            is_last = index == len(self._segments) - 1
            painter.setBrush(QColor(segment.color))
            painter.drawRoundedRect(
                QRectF(left, 0, width - (0 if is_last else gap), self.HEIGHT), radius, radius
            )
            left += width
        painter.end()
