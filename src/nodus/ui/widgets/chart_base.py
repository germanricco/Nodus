"""What the dashboard charts share: the transition between data, tooltips and scales.

Charts are painted with QPainter rather than QtCharts so they follow the theme tokens and
can morph from the figures they showed to the new ones, which QtCharts cannot do because
it rebuilds its series.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from typing import TypeVar

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QShowEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.ui.theme.design import TextRole, role_font
from nodus.ui.theme.theme import Theme

# Length of every chart and figure transition. Tests set it to 0 to check the final state.
DURATION_MS = 450

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
    result.setAlphaF(max(0.0, min(1.0, alpha)))
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
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._advance)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def _start_transition(self) -> None:
        """Called by subclasses after storing new data."""
        self._animation.stop()
        if DURATION_MS <= 0:
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
        self._animation.setDuration(DURATION_MS)
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
        padding, spacing = 10.0, 3.0
        width = max(
            [title_metrics.horizontalAdvance(title)]
            + [line_metrics.horizontalAdvance(line) for line in lines]
        )
        width += 2 * padding
        height = (
            2 * padding + title_metrics.height() + len(lines) * (line_metrics.height() + spacing)
        )
        x = anchor.x() + 12
        if x + width > self.width() - 2:
            x = anchor.x() - 12 - width
        y = max(2.0, min(anchor.y() - height / 2, self.height() - height - 2))
        box = QRectF(max(2.0, x), y, width, height)

        painter.save()
        painter.setPen(with_alpha(self._theme.border, 1))
        painter.setBrush(QColor(self._theme.surface))
        painter.drawRoundedRect(box, 8, 8)
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

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.hover_index = None
        self.update()


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
