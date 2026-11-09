"""Smooth line with a gradient area, for the net worth trend."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import QWidget

from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.chart_base import (
    ColumnHoverChart,
    lerp,
    resample,
    starting_values,
    with_alpha,
)

# Up/down dots are drawn only while they stay readable.
MAX_CHANGE_DOTS = 31
# Minimum room between two day labels under the chart, in pixels.
AXIS_LABEL_GAP = 16


@dataclass(frozen=True)
class LinePoint:
    """A day and its value (in cents), or None where the value is unknown."""

    day: date
    value: float | None


def value_range(values: list[float]) -> tuple[float, float]:
    """The vertical span to draw, padded so the line never touches the edges; a flat
    series gets room around it."""
    if not values:
        return 0.0, 1.0
    low, high = min(values), max(values)
    if high == low:
        margin = abs(high) * 0.1 or 100.0
        return low - margin, high + margin
    margin = (high - low) * 0.12
    return low - margin, high + margin


def axis_indexes(count: int, fit: int) -> list[int]:
    """The points to label under the chart: every point when they all fit, otherwise one
    every few at a regular step. The last point (usually today) is always labeled; it takes
    the place of the previous label when they are less than a step apart, since the step
    is the least distance at which labels fit."""
    if count == 0:
        return []
    step = max(1, -(-count // max(fit, 1)))
    indexes = list(range(0, count, step))
    last = count - 1
    if indexes[-1] != last:
        if last - indexes[-1] < step and len(indexes) > 1:
            indexes[-1] = last
        else:
            indexes.append(last)
    return indexes


def change_directions(values: list[float | None]) -> list[int]:
    """For each point: 1 if it rose from the previous known value, -1 if it fell, 0 else."""
    directions, previous = [], None
    for value in values:
        if value is None or previous is None or value == previous:
            directions.append(0)
        else:
            directions.append(1 if value > previous else -1)
        if value is not None:
            previous = value
    return directions


class LineChart(ColumnHoverChart):
    """The trend of a value over days.

    The first time it draws itself from left to right; later it morphs from the previous
    line into the new one. Under the mouse, a vertical guide follows the cursor and a box
    shows the day and the value. Points where the value rose or fell get a green or red dot.
    """

    LEFT, BOTTOM, TOP, RIGHT = 64.0, 24.0, 10.0, 10.0

    def __init__(
        self,
        theme: Theme,
        format_value: Callable[[float], str],
        format_axis: Callable[[float], str],
        format_day: Callable[[date], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(theme, parent)
        self._format_value = format_value
        self._format_axis = format_axis
        self._format_day = format_day
        self._points: list[LinePoint] = []
        # Where each point begins the transition; None the first time, when the line
        # draws itself from left to right instead.
        self._start: list[float | None] | None = None
        self.setMinimumHeight(180)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, 220)

    def set_points(self, points: list[LinePoint]) -> None:
        """Shows ``points``, moving from what was shown before."""
        if points == self._points:
            return
        shown = {
            point.day: value
            for point, value in zip(self._points, self._values_at(self.progress), strict=True)
            if value is not None
        }
        self._start = self._starts(points, shown) if shown else None
        self._points = points
        self.hover_index = None
        self._start_transition()

    def points(self) -> list[LinePoint]:
        return self._points

    @staticmethod
    def _starts(points: list[LinePoint], shown: dict[date, float]) -> list[float | None]:
        """Each day begins where it was on screen, so a change in the data (a new
        transaction, another currency) moves only what changed. A day that was not shown
        appears at its value. With no day in common (another period), the old line's shape
        morphs into the new one point by point."""
        if any(point.day in shown for point in points):
            return starting_values(shown, [p.day for p in points], None)
        return list(resample(list(shown.values()), len(points)))

    def _values_at(self, progress: float) -> list[float | None]:
        """The values on screen at ``progress`` of the transition."""
        targets = [p.value for p in self._points]
        if self._start is None or progress >= 1:
            return targets
        return [
            None if target is None else lerp(target if begin is None else begin, target, progress)
            for begin, target in zip(self._start, targets, strict=True)
        ]

    # Geometry

    def _plot_rect(self) -> QRectF:
        return QRectF(
            self.LEFT,
            self.TOP,
            max(1.0, self.width() - self.LEFT - self.RIGHT),
            max(1.0, self.height() - self.TOP - self.BOTTOM),
        )

    def _x(self, index: int, plot: QRectF) -> float:
        count = len(self._points)
        if count <= 1:
            return plot.center().x()
        return plot.left() + plot.width() * index / (count - 1)

    def _positions(self, values: list[float | None], plot: QRectF) -> list[QPointF | None]:
        low, high = value_range([v for v in values if v is not None])
        span = high - low
        return [
            None
            if value is None
            else QPointF(self._x(i, plot), plot.bottom() - plot.height() * (value - low) / span)
            for i, value in enumerate(values)
        ]

    # Painting

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot_rect()
        values = self._values_at(self.progress)
        known = [v for v in values if v is not None]
        self._paint_grid(painter, plot, known)
        if not known:
            painter.end()
            return
        positions = self._positions(values, plot)
        if self._start is None and self.progress < 1:
            # First appearance: reveal from left to right.
            painter.setClipRect(
                QRectF(0, 0, plot.left() + plot.width() * self.progress + 2, self.height())
            )
        for run in self._runs(positions):
            self._paint_run(painter, run, plot)
        painter.setClipping(False)
        self._paint_change_dots(painter, positions)
        if self.hover_index is not None and positions[self.hover_index] is not None:
            self._paint_hover(painter, positions[self.hover_index], plot)
        painter.end()

    def _paint_grid(self, painter: QPainter, plot: QRectF, known: list[float]) -> None:
        low, high = value_range(known)
        small = QFont(self.font())
        small.setPointSizeF(self.font().pointSizeF() * 0.85)
        painter.setFont(small)
        for step in range(3):
            y = plot.bottom() - plot.height() * step / 2
            painter.setPen(QPen(with_alpha(self._theme.border, 0.8), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            if known:
                painter.setPen(QColor(self._theme.text_muted))
                painter.drawText(
                    QRectF(0, y - 9, self.LEFT - 8, 18),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    self._format_axis(lerp(low, high, step / 2)),
                )
        painter.setPen(QColor(self._theme.text_muted))
        for index in self._axis_indexes(plot, painter):
            # Centered under its point, but kept inside the widget at both ends.
            left = min(max(self._x(index, plot) - 40, 0), self.width() - 80)
            painter.drawText(
                QRectF(left, plot.bottom() + 4, 80, self.BOTTOM - 4),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self._format_day(self._points[index].day),
            )

    def _axis_indexes(self, plot: QRectF, painter: QPainter) -> list[int]:
        """As many days as fit side by side under the plot without overlapping."""
        if not self._points:
            return []
        metrics = painter.fontMetrics()
        widest = max(metrics.horizontalAdvance(self._format_day(p.day)) for p in self._points)
        return axis_indexes(len(self._points), int(plot.width() // (widest + AXIS_LABEL_GAP)) + 1)

    @staticmethod
    def _runs(positions: list[QPointF | None]) -> list[list[QPointF]]:
        """Stretches of consecutive known points; unknown values break the line."""
        runs, current = [], []
        for position in positions:
            if position is None:
                if current:
                    runs.append(current)
                current = []
            else:
                current.append(position)
        if current:
            runs.append(current)
        return runs

    def _paint_run(self, painter: QPainter, run: list[QPointF], plot: QRectF) -> None:
        line = QPainterPath(run[0])
        for previous, point in zip(run, run[1:], strict=False):
            third = (point.x() - previous.x()) / 3
            line.cubicTo(
                QPointF(previous.x() + third, previous.y()),
                QPointF(point.x() - third, point.y()),
                point,
            )
        area = QPainterPath(line)
        area.lineTo(run[-1].x(), plot.bottom())
        area.lineTo(run[0].x(), plot.bottom())
        area.closeSubpath()
        gradient = QLinearGradient(0, plot.top(), 0, plot.bottom())
        gradient.setColorAt(0, with_alpha(self._theme.accent, 0.32))
        gradient.setColorAt(1, with_alpha(self._theme.accent, 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(area)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(self._theme.accent), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(line)
        if len(run) == 1:
            painter.setBrush(QColor(self._theme.accent))
            painter.drawEllipse(run[0], 3, 3)

    def _paint_change_dots(self, painter: QPainter, positions: list[QPointF | None]) -> None:
        directions = change_directions([p.value for p in self._points])
        changes = [i for i, d in enumerate(directions) if d]
        if not changes or len(changes) > MAX_CHANGE_DOTS:
            return
        plot = self._plot_rect()
        # While the line draws itself, dots appear as it reaches them.
        revealed = plot.left() + plot.width() * (self.progress if self._start is None else 1)
        for index in changes:
            position = positions[index]
            if position is None or position.x() > revealed + 1:
                continue
            color = self._theme.income if directions[index] > 0 else self._theme.expense
            painter.setPen(QPen(QColor(self._theme.surface), 2))
            painter.setBrush(QColor(color))
            painter.drawEllipse(position, 5, 5)

    def _paint_hover(self, painter: QPainter, point: QPointF, plot: QRectF) -> None:
        painter.setPen(QPen(with_alpha(self._theme.text_muted, 0.7), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(point.x(), plot.top()), QPointF(point.x(), plot.bottom()))
        painter.setPen(QPen(QColor(self._theme.accent), 3))
        painter.setBrush(QColor(self._theme.surface))
        painter.drawEllipse(point, 6, 6)
        hovered = self._points[self.hover_index]
        self.paint_tooltip(
            painter, point, self._format_day_long(hovered.day), [self._format_value(hovered.value)]
        )

    @staticmethod
    def _format_day_long(day: date) -> str:
        return day.strftime("%d/%m/%Y")

    # Mouse

    def index_at(self, x: float) -> int | None:
        """The known point closest to ``x``, or None when there is none."""
        known = [i for i, p in enumerate(self._points) if p.value is not None]
        if not known:
            return None
        plot = self._plot_rect()
        return min(known, key=lambda i: abs(self._x(i, plot) - x))
