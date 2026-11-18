"""What every chart shares: the transition between data, tooltips and scales.

Charts are painted with QPainter rather than QtCharts so they follow the theme tokens and
can morph from the figures they showed to the new ones, which QtCharts cannot do because
it rebuilds its series.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from typing import Protocol, TypeVar

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QShowEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.ui.theme.design import (
    Easing,
    Line,
    Motion,
    Radius,
    TextRole,
    Tooltip,
    motion_ms,
    role_font,
)
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.style import unit_animation

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


def lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * progress


def starting_values(shown: Mapping[K, V], keys: Sequence[K], baseline: V) -> list[V]:
    """Where each new item begins its transition: where the item with the same key was on
    screen, or ``baseline`` if it is new.

    Charts match old and new data by identity (a day, a month, a category), never by
    position: a list can lose, gain or shift items, and matching by position would make
    each one start from another's place.
    """
    return [shown.get(key, baseline) for key in keys]


def resample(values: Sequence[float], count: int) -> list[float]:
    """``values`` stretched or shrunk to ``count`` items by linear interpolation, so a
    series can morph into one of another length."""
    if count <= 0:
        return []
    if not values:
        return [0.0] * count
    if len(values) == 1 or count == 1:
        return [float(values[-1])] * count
    last = len(values) - 1
    result = []
    for i in range(count):
        position = i * last / (count - 1)
        low = int(position)
        high = min(low + 1, last)
        result.append(lerp(values[low], values[high], position - low))
    return result


def with_alpha(color: str, alpha: float) -> QColor:
    """``color`` with an opacity from 0 to 1."""
    result = QColor(color)
    result.setAlphaF(alpha)
    return result


def format_compact(cents: float, currency: Currency) -> str:
    """Short axis labels: "$ 2,9 M", "US$ 15 k", "$ 950"."""
    amount = cents / 100
    symbol = Money.zero(currency).format().split(" ")[0].lstrip("-")
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    for limit, suffix in ((1_000_000, "M"), (1_000, "k")):
        if amount >= limit:
            value = amount / limit
            text = f"{value:.1f}" if value < 10 else f"{value:.0f}"
            return f"{sign}{symbol} {text.replace('.', ',').removesuffix(',0')} {suffix}"
    return f"{sign}{symbol} {amount:.0f}"


class AnimatedChart(QWidget):
    """Base for charts that move from the previous data to the new one.

    Subclasses keep the "from" and "to" data and paint the mix given by ``progress``
    (0 → 1). Data that arrives while the chart is hidden plays its transition when the
    chart is shown, so a chart grows the first time it appears.
    """

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.progress = 1.0
        self._pending = False
        self._animation = unit_animation(self, Easing.SETTLE, self._advance)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def make_strip(self, height: int) -> None:
        """Makes the chart a thin bar across its row, ``height`` tall, with nothing to
        show under the mouse: a budget's, a goal's, a proportion's."""
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(False)

    def _start_transition(self) -> None:
        """Called by subclasses after storing new data."""
        self._animation.stop()
        if motion_ms(Motion.SLOW) <= 0:
            self.progress = 1.0
            self._pending = False
        elif self.isVisible():
            self._play()
        else:
            self.progress = 0.0
            self._pending = True
        self.update()

    def _play(self) -> None:
        self._pending = False
        self.progress = 0.0
        self._animation.setDuration(motion_ms(Motion.SLOW))
        self._animation.start()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._pending:
            self._play()

    def _advance(self, value: float) -> None:
        self.progress = float(value)
        self.update()

    def paint_tooltip(
        self, painter: QPainter, anchor: QPointF, title: str, lines: Sequence[str]
    ) -> None:
        """A floating box near ``anchor`` with a muted ``title`` and bold ``lines``, kept
        inside the widget."""
        title_font = role_font(TextRole.NOTE)
        line_font = role_font(TextRole.BODY)
        line_font.setWeight(QFont.Weight.DemiBold)
        title_metrics, line_metrics = QFontMetricsF(title_font), QFontMetricsF(line_font)
        padding, spacing, margin = Tooltip.PADDING, Tooltip.LINE_SPACING, Tooltip.MARGIN
        width = max(
            [title_metrics.horizontalAdvance(title)]
            + [line_metrics.horizontalAdvance(line) for line in lines]
        )
        width += 2 * padding
        height = (
            2 * padding + title_metrics.height() + len(lines) * (line_metrics.height() + spacing)
        )
        x = anchor.x() + Tooltip.OFFSET
        if x + width > self.width() - margin:
            x = anchor.x() - Tooltip.OFFSET - width
        y = max(margin, min(anchor.y() - height / 2, self.height() - height - margin))
        box = QRectF(max(margin, x), y, width, height)

        painter.save()
        painter.setPen(QColor(self._theme.border))
        painter.setBrush(QColor(self._theme.surface))
        painter.drawRoundedRect(box, Radius.L, Radius.L)
        painter.setFont(title_font)
        painter.setPen(QColor(self._theme.text_muted))
        top = box.top() + padding
        painter.drawText(
            QRectF(box.left() + padding, top, width, title_metrics.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )
        top += title_metrics.height() + spacing
        painter.setFont(line_font)
        painter.setPen(QColor(self._theme.text))
        for line in lines:
            painter.drawText(
                QRectF(box.left() + padding, top, width, line_metrics.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )
            top += line_metrics.height() + spacing
        painter.restore()


class ProgressStrip(AnimatedChart):
    """A thin bar filled to ``fraction``: a budget's, a goal's.

    Pages build their rows anew on every refresh, so a strip starts from what the strip
    it replaces was showing (``start``, from ``shown_fractions``): one whose figure did
    not change stays still, as when amounts are hidden or the theme changes, and one that
    changed moves from its old figure. A strip seen for the first time grows from empty.
    """

    def __init__(
        self, theme: Theme, height: int, start: float | None, parent: QWidget | None = None
    ) -> None:
        super().__init__(theme, parent)
        self.make_strip(height)
        self._start = 0.0 if start is None else start

    @property
    def fraction(self) -> float:
        """How full the strip ends up; past 1 for a budget over its limit."""
        raise NotImplementedError

    @property
    def shown_fraction(self) -> float:
        """How full the strip is painted now, partway through its transition."""
        return lerp(self._start, self.fraction, self.progress)

    def _begin(self) -> None:
        """Called by subclasses once their data is stored."""
        if self._start != self.fraction:
            self._start_transition()


def shown_fractions(strips: Mapping[K, ProgressStrip]) -> dict[K, float]:
    """What each strip shows now, by the key of what it stands for (a goal, a category),
    for the strips that replace them to start from."""
    return {key: strip.shown_fraction for key, strip in strips.items()}


class ColumnHoverChart(AnimatedChart):
    """A chart of one column per point, the one under the mouse in ``hover_index``.
    Subclasses say which column an x falls in through ``index_at``."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(theme, parent)
        self.hover_index: int | None = None

    def index_at(self, x: float) -> int | None:
        raise NotImplementedError

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.index_at(event.position().x())
        if index != self.hover_index:
            self.hover_index = index
            self.update()

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.hover_index = None
        self.update()


class BarColumn(Protocol):
    """What a bar chart's column shows besides its bars: a label and a tooltip."""

    label: str
    tooltip_title: str
    tooltip_lines: tuple[str, ...]


class BarColumnsChart(ColumnHoverChart):
    """Bars in equal columns, a label under each and a baseline across: what the cash
    flow and the trend charts share. Subclasses give their columns and draw the bars."""

    BOTTOM = 22.0  # geometry: room for the labels under the axis

    def columns(self) -> Sequence[BarColumn]:
        raise NotImplementedError

    def slots(self) -> list[QRectF]:
        """The column each bar group occupies, full height."""
        return column_slots(len(self.columns()), self.width(), self.height())

    def index_at(self, x: float) -> int | None:
        return slot_index(self.slots(), x)

    def paint_label(self, painter: QPainter, slot: QRectF, text: str, selected: bool) -> None:
        """``text`` under the axis, bolder and darker for the column being viewed."""
        font = role_font(TextRole.NOTE)
        font.setWeight(QFont.Weight.DemiBold if selected else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(self._theme.text if selected else self._theme.text_muted))
        painter.drawText(
            QRectF(slot.left(), self.height() - self.BOTTOM + 4, slot.width(), self.BOTTOM - 4),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            text,
        )

    def paint_baseline(self, painter: QPainter, y: float) -> None:
        painter.setPen(QPen(QColor(self._theme.border), Line.THIN))
        painter.drawLine(QPointF(0, y), QPointF(self.width(), y))

    def paint_hover(self, painter: QPainter) -> None:
        """The tooltip of the column under the mouse, if any, at its middle."""
        if self.hover_index is None:
            return
        column = self.columns()[self.hover_index]
        center = QPointF(self.slots()[self.hover_index].center().x(), self.height() / 2)
        self.paint_tooltip(painter, center, column.tooltip_title, column.tooltip_lines)

    def clicked_index(self, event: QMouseEvent) -> int | None:
        """The column a left click fell on, if any."""
        if event.button() is not Qt.MouseButton.LeftButton:
            return None
        return self.index_at(event.position().x())


def column_slots(count: int, width: float, height: float) -> list[QRectF]:
    """``count`` equal columns across a chart, full height: the place of each bar group."""
    if count == 0:
        return []
    column = width / count
    return [QRectF(i * column, 0, column, height) for i in range(count)]


def slot_index(slots: list[QRectF], x: float) -> int | None:
    """The column under ``x``, if any."""
    return next((i for i, slot in enumerate(slots) if slot.left() <= x < slot.right()), None)


def rounded_bar_path(rect: QRectF, radius: float, round_top: bool) -> QPainterPath:
    """A bar with only its outer end rounded: the top for positive values, the bottom for
    negative ones, so bars stand on the baseline."""
    path = QPainterPath()
    radius = min(radius, rect.width() / 2, rect.height())
    if rect.height() <= 0 or rect.width() <= 0:
        return path
    if round_top:
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + radius)
        path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
        path.lineTo(rect.right() - radius, rect.top())
        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
        path.lineTo(rect.right(), rect.bottom())
    else:
        path.moveTo(rect.left(), rect.top())
        path.lineTo(rect.left(), rect.bottom() - radius)
        path.quadTo(rect.left(), rect.bottom(), rect.left() + radius, rect.bottom())
        path.lineTo(rect.right() - radius, rect.bottom())
        path.quadTo(rect.right(), rect.bottom(), rect.right(), rect.bottom() - radius)
        path.lineTo(rect.right(), rect.top())
    path.closeSubpath()
    return path
