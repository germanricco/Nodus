"""Bars standing on a zero line, for the month-by-month cash flow."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.chart_base import AnimatedChart, lerp, rounded_bar_path, with_alpha


@dataclass(frozen=True)
class Bar:
    """One bar: its label under the axis, its value (positive goes up, negative down) and
    the lines of its tooltip. ``selected`` marks the bar of the period being viewed."""

    label: str
    value: float
    tooltip_title: str
    tooltip_lines: tuple[str, ...]
    selected: bool = False


class BarChart(AnimatedChart):
    """Green bars for positive values and red ones for negative, like the reference.

    Bars grow from the zero line the first time and resize to new values afterwards. The
    bar under the mouse lights up, the others fade, and a box shows its details.
    """

    BOTTOM, TOP = 22.0, 8.0
    GAP_RATIO = 0.35

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(theme, parent)
        self._bars: list[Bar] = []
        self._previous: list[float] = []
        self.hover_index: int | None = None
        self.setMinimumHeight(120)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(320, 150)

    def set_bars(self, bars: list[Bar]) -> None:
        if bars == self._bars:
            return
        shown = self._values_at(self.progress)
        # Bars keep their place when the count stays; otherwise they grow from zero.
        self._previous = shown if len(shown) == len(bars) else [0.0] * len(bars)
        self._bars = bars
        self.hover_index = None
        self._start_transition()

    def bars(self) -> list[Bar]:
        return self._bars

    def _values_at(self, progress: float) -> list[float]:
        targets = [bar.value for bar in self._bars]
        if len(self._previous) != len(targets):
            return targets
        return [lerp(a, b, progress) for a, b in zip(self._previous, targets, strict=True)]

    def _slots(self) -> list[QRectF]:
        """The column each bar occupies, full height."""
        count = len(self._bars)
        if count == 0:
            return []
        width = self.width() / count
        return [QRectF(i * width, 0, width, self.height()) for i in range(count)]

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        values = self._values_at(self.progress)
        top, bottom = self.TOP, self.height() - self.BOTTOM
        largest = max([abs(b.value) for b in self._bars] + [abs(v) for v in values] + [1.0])
        has_negative = any(b.value < 0 for b in self._bars)
        has_positive = any(b.value > 0 for b in self._bars) or not has_negative
        if has_negative and has_positive:
            zero = top + (bottom - top) * 0.62
        else:
            zero = bottom if has_positive else top
        up_room, down_room = zero - top, bottom - zero
        scale_room = max(up_room, down_room)

        small = QFont(self.font())
        small.setPointSizeF(self.font().pointSizeF() * 0.85)
        painter.setFont(small)
        for index, (slot, bar, value) in enumerate(
            zip(self._slots(), self._bars, values, strict=True)
        ):
            inset = slot.width() * self.GAP_RATIO / 2
            height = scale_room * abs(value) / largest
            height = min(height, up_room if value >= 0 else down_room)
            if value >= 0:
                rect = QRectF(slot.left() + inset, zero - height, slot.width() - 2 * inset, height)
            else:
                rect = QRectF(slot.left() + inset, zero, slot.width() - 2 * inset, height)
            color = self._theme.income if bar.value >= 0 else self._theme.expense
            faded = self.hover_index is not None and index != self.hover_index
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(with_alpha(color, 0.35 if faded else 0.9))
            if height < 2 and abs(bar.value) > 0:
                rect = QRectF(rect.left(), zero - (2 if value >= 0 else 0), rect.width(), 2)
            painter.drawPath(rounded_bar_path(rect, 5, value >= 0))
            font = QFont(small)
            font.setWeight(QFont.Weight.DemiBold if bar.selected else QFont.Weight.Normal)
            painter.setFont(font)
            painter.setPen(QColor(self._theme.text if bar.selected else self._theme.text_muted))
            painter.drawText(
                QRectF(slot.left(), bottom + 4, slot.width(), self.BOTTOM - 4),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                bar.label,
            )
        painter.setPen(QPen(with_alpha(self._theme.border, 1), 1))
        painter.drawLine(QPointF(0, zero), QPointF(self.width(), zero))
        if self.hover_index is not None:
            slot = self._slots()[self.hover_index]
            bar = self._bars[self.hover_index]
            self.paint_tooltip(
                painter, QPointF(slot.center().x(), self.height() / 2), bar.tooltip_title,
                bar.tooltip_lines,
            )  # fmt: skip
        painter.end()

    def index_at(self, x: float) -> int | None:
        for index, slot in enumerate(self._slots()):
            if slot.left() <= x < slot.right():
                return index
        return None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.index_at(event.position().x())
        if index != self.hover_index:
            self.hover_index = index
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.hover_index = None
        self.update()
