"""Paired income and expense bars, for the month-by-month cash flow."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from nodus.ui.theme.design import Chart, Line, Opacity, Radius, TextRole, role_font
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.chart_base import (
    ColumnHoverChart,
    column_slots,
    lerp,
    rounded_bar_path,
    slot_index,
    starting_values,
    with_alpha,
)


@dataclass(frozen=True)
class BarGroup:
    """One month: its label under the axis, what came in and what went out (both as
    positive amounts) and the lines of its tooltip. ``selected`` marks the month being
    viewed, and ``key`` tells it apart from the others (the label repeats every year)."""

    label: str
    income: float
    expenses: float
    tooltip_title: str
    tooltip_lines: tuple[str, ...]
    selected: bool = False
    key: Hashable = None

    @property
    def identity(self) -> Hashable:
        return self.label if self.key is None else self.key


class BarChart(ColumnHoverChart):
    """A green income bar next to a red expense bar for each month, so both sides of the
    result can be compared at a glance.

    Bars grow from the baseline the first time and resize to new values afterwards. The
    month under the mouse lights up, the others fade, and a box shows its details.
    Clicking a month emits ``clicked`` with its index.
    """

    clicked = Signal(int)

    BOTTOM, TOP = 22.0, 8.0  # geometry: room for the axis labels
    GROUP_GAP_RATIO = 0.3  # geometry

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(theme, parent)
        self._groups: list[BarGroup] = []
        # Where each bar begins the transition, in the order of ``_groups``.
        self._previous: list[tuple[float, float]] = []
        self.setMinimumHeight(Chart.BAR_MIN_HEIGHT)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(*Chart.BAR_SIZE)

    def set_groups(self, groups: list[BarGroup]) -> None:
        if groups == self._groups:
            return
        values = self._values_at(self.progress)
        shown = dict(zip((g.identity for g in self._groups), values, strict=True))
        # A month on screen resizes from where it is; a new one grows from the baseline.
        self._previous = starting_values(shown, [g.identity for g in groups], (0.0, 0.0))
        self._groups = groups
        self.hover_index = None
        self._start_transition()

    def groups(self) -> list[BarGroup]:
        return self._groups

    def _values_at(self, progress: float) -> list[tuple[float, float]]:
        """The (income, expenses) heights on screen at ``progress``, never below zero."""
        targets = [(max(g.income, 0.0), max(g.expenses, 0.0)) for g in self._groups]
        if len(self._previous) != len(targets):
            return targets
        return [
            (lerp(begin[0], end[0], progress), lerp(begin[1], end[1], progress))
            for begin, end in zip(self._previous, targets, strict=True)
        ]

    def _slots(self) -> list[QRectF]:
        """The column each month occupies, full height."""
        return column_slots(len(self._groups), self.width(), self.height())

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        values = self._values_at(self.progress)
        top, baseline = self.TOP, self.height() - self.BOTTOM
        room = baseline - top
        largest = max([v for pair in values for v in pair] + [1.0])

        small = role_font(TextRole.NOTE)
        for index, (slot, group, pair) in enumerate(
            zip(self._slots(), self._groups, values, strict=True)
        ):
            faded = self.hover_index is not None and index != self.hover_index
            inner = slot.width() * (1 - self.GROUP_GAP_RATIO)
            bar_width = min((inner - Chart.BAR_PAIR_GAP) / 2, Chart.BAR_MAX_WIDTH)
            left = slot.center().x() - bar_width - Chart.BAR_PAIR_GAP / 2
            for offset, value, color in (
                (0.0, pair[0], self._theme.income),
                (bar_width + Chart.BAR_PAIR_GAP, pair[1], self._theme.expense),
            ):
                if value <= 0:
                    continue
                height = max(room * value / largest, 2.0)
                rect = QRectF(left + offset, baseline - height, bar_width, height)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(with_alpha(color, Opacity.FADED if faded else Opacity.BAR))
                painter.drawPath(rounded_bar_path(rect, Radius.S, True))
            font = QFont(small)
            font.setWeight(QFont.Weight.DemiBold if group.selected else QFont.Weight.Normal)
            painter.setFont(font)
            painter.setPen(QColor(self._theme.text if group.selected else self._theme.text_muted))
            painter.drawText(
                QRectF(slot.left(), baseline + 4, slot.width(), self.BOTTOM - 4),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                group.label,
            )
        painter.setPen(QPen(QColor(self._theme.border), Line.THIN))
        painter.drawLine(QPointF(0, baseline), QPointF(self.width(), baseline))
        if self.hover_index is not None:
            slot = self._slots()[self.hover_index]
            group = self._groups[self.hover_index]
            self.paint_tooltip(
                painter, QPointF(slot.center().x(), self.height() / 2), group.tooltip_title,
                group.tooltip_lines,
            )  # fmt: skip
        painter.end()

    def index_at(self, x: float) -> int | None:
        return slot_index(self._slots(), x)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.index_at(event.position().x())
        if index is not None and event.button() is Qt.MouseButton.LeftButton:
            self.clicked.emit(index)
