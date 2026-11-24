"""Bars split by category, one per month, for the long trends of the analysis page."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal, SignalInstance
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from nodus.i18n import _
from nodus.ui.theme.design import Chart, Line, Opacity, Radius
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.charts.chart_base import (
    BarColumnsChart,
    lerp,
    rounded_bar_path,
    starting_values,
    value_axis,
    with_alpha,
)


@dataclass(frozen=True)
class StackSegment:
    """A piece of a bar: a category (``key`` is its id) with its color and value in cents.

    A negative value hangs below the baseline, as a month that ended with less money.
    """

    key: int | None
    color: str
    value: float


@dataclass(frozen=True)
class StackedBar:
    """One month: its label under the axis, its pieces from the bottom up and the lines
    of its tooltip. ``key`` tells it apart from the others (the label repeats every year)."""

    label: str
    segments: tuple[StackSegment, ...]
    tooltip_title: str
    tooltip_lines: tuple[str, ...]
    key: Hashable = None

    @property
    def identity(self) -> Hashable:
        return self.label if self.key is None else self.key

    @property
    def has_data(self) -> bool:
        return any(segment.value for segment in self.segments)


class StackedBarChart(BarColumnsChart):
    """A bar per month, stacked by category, with a dashed line at the monthly average.

    Bars grow the first time and each piece resizes to its new value afterwards, matched
    by category. The month under the mouse lights up with a box of details; a click emits
    ``clicked`` with the month's index and the category under the cursor (None between
    pieces).
    """

    clicked = Signal(int, object)  # bar index, segment key or None

    TOP = 18.0  # geometry: room for the totals
    GAP_RATIO = 0.35  # geometry

    def __init__(
        self,
        theme: Theme,
        format_value: Callable[[float], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(theme, format_value, parent)
        self._format_value = format_value
        self._bars: list[StackedBar] = []
        self._previous: list[dict[int | None, float]] = []
        self.average: float | None = None
        self.setMinimumHeight(Chart.STACKED_MIN_HEIGHT)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(*Chart.STACKED_SIZE)

    def set_bars(self, bars: list[StackedBar], average: float | None = None) -> None:
        if bars == self._bars and average == self.average:
            return
        shown = {
            old.identity: {s.key: v for s, v in zip(old.segments, values, strict=True)}
            for old, values in zip(self._bars, self._values_at(self.progress), strict=True)
        }
        # A month on screen resizes each piece from where it is; a new one grows from the
        # baseline.
        self._previous = starting_values(shown, [bar.identity for bar in bars], {})
        self._bars = bars
        self.average = average
        self.hover_index = None
        self._start_transition()

    def click_signal(self) -> SignalInstance:
        return self.clicked

    def bars(self) -> list[StackedBar]:
        return self._bars

    def columns(self) -> list[StackedBar]:
        return self._bars

    def _values_at(self, progress: float) -> list[list[float]]:
        """The value of each piece on screen at ``progress``."""
        if len(self._previous) != len(self._bars):
            return [[s.value for s in bar.segments] for bar in self._bars]
        return [
            [lerp(before.get(s.key, 0.0), s.value, progress) for s in bar.segments]
            for bar, before in zip(self._bars, self._previous, strict=True)
        ]

    # Geometry

    def _axis(self, values: list[list[float]]) -> list[float]:
        """The values of the guides, from the lowest stack (or zero) to the highest."""
        highest = max([sum(v for v in bar if v > 0) for bar in values] + [0.0])
        lowest = min([sum(v for v in bar if v < 0) for bar in values] + [0.0])
        if self.average is not None:
            highest, lowest = max(highest, self.average), min(lowest, self.average)
        return value_axis(lowest, highest)

    def _scale(self, values: list[list[float]]) -> tuple[float, float]:
        """The baseline's height on screen and the pixels per cent."""
        axis = self._axis(values)
        highest, lowest = axis[-1], axis[0]
        span = (highest - lowest) or 1.0
        room = self.height() - self.TOP - self.BOTTOM
        per_cent = room / span
        return self.TOP + highest * per_cent, per_cent

    def _pieces(
        self, index: int, values: list[float], baseline: float, per_cent: float
    ) -> list[tuple[StackSegment, QRectF]]:
        """Where each piece of bar ``index`` is drawn: positives stack up from the
        baseline, negatives down from it."""
        slot = self.slots()[index]
        width = min(slot.width() * (1 - self.GAP_RATIO), Chart.STACKED_BAR_MAX_WIDTH)
        left = slot.center().x() - width / 2
        up = down = baseline
        pieces = []
        for segment, value in zip(self._bars[index].segments, values, strict=True):
            height = abs(value) * per_cent
            if height <= 0:
                continue
            if value > 0:
                up -= height
                pieces.append((segment, QRectF(left, up, width, height)))
            else:
                pieces.append((segment, QRectF(left, down, width, height)))
                down += height
        return pieces

    def segment_at(self, point: QPointF) -> tuple[int | None, int | None]:
        """The bar and the category under ``point``; the category is None between pieces."""
        index = self.index_at(point.x())
        if index is None:
            return None, None
        values = self._values_at(self.progress)
        baseline, per_cent = self._scale(values)
        for segment, rect in self._pieces(index, values[index], baseline, per_cent):
            if rect.top() <= point.y() <= rect.bottom():
                return index, segment.key
        return index, None

    # Painting

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        all_values = self._values_at(self.progress)
        baseline, per_cent = self._scale(all_values)
        self.paint_guides(painter, [(baseline - v * per_cent, v) for v in self._axis(all_values)])
        for index, (slot, bar, values) in enumerate(
            zip(self.slots(), self._bars, all_values, strict=True)
        ):
            faded = self.hover_index is not None and index != self.hover_index
            pieces = self._pieces(index, values, baseline, per_cent)
            outer_up = max((i for i, (s, _rect) in enumerate(pieces) if s.value > 0), default=None)
            outer_down = max(
                (i for i, (s, _rect) in enumerate(pieces) if s.value < 0), default=None
            )
            painter.setPen(Qt.PenStyle.NoPen)
            for position, (segment, rect) in enumerate(pieces):
                painter.setBrush(with_alpha(segment.color, Opacity.FADED if faded else Opacity.BAR))
                if position in (outer_up, outer_down):
                    painter.drawPath(rounded_bar_path(rect, Radius.S, position == outer_up))
                else:
                    painter.drawRect(rect)
            self.paint_label(painter, slot, bar.label, selected=False)
        self.paint_baseline(painter, baseline)
        if self.average is not None and self._bars:
            self._paint_average(painter, baseline - self.average * per_cent)
        self.paint_hover(painter)
        painter.end()

    def _paint_average(self, painter: QPainter, y: float) -> None:
        pen = QPen(QColor(self._theme.warning), Line.STROKE, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(self.LEFT, y), QPointF(self.width(), y))
        # The label sits on a patch of the card's color, so it reads over a bar.
        text = _("Promedio {amount}").format(amount=self._format_value(self.average))
        width = painter.fontMetrics().horizontalAdvance(text) + 12
        box = QRectF(self.width() - width, y - 18, width, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._theme.surface))
        painter.drawRoundedRect(box, Radius.S, Radius.S)
        painter.setPen(QColor(self._theme.warning))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    # Mouse

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.clicked_index(event) is not None:
            self.clicked.emit(*self.segment_at(event.position()))
