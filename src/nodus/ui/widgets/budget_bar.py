"""How a budget is drawn: its progress bar against the pace of the month, its pill and texts."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from nodus.models.budget import Budget, BudgetState, used_percent_label
from nodus.ui.theme.design import ControlSize, Line, Opacity
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.chart_base import AnimatedChart, format_compact, lerp, with_alpha
from nodus.ui.widgets.style import set_style_property

STATE_TONES = {
    BudgetState.ON_TRACK: "good",
    BudgetState.AHEAD: "warning",
    BudgetState.OVER: "bad",
}


def state_color(theme: Theme, state: BudgetState) -> str:
    """Green while on track, amber when spending runs ahead of the month, red when over."""
    return {
        BudgetState.ON_TRACK: theme.income,
        BudgetState.AHEAD: theme.warning,
        BudgetState.OVER: theme.expense,
    }[state]


def spent_of_limit(budget: Budget, compact: bool = False) -> str:
    """ "$ 260.000,00 de $ 400.000,00", or "$ 260 k de $ 400 k" where room is short."""
    if compact:
        currency = budget.limit.currency
        return (
            f"{format_compact(budget.spent.cents, currency)} de "
            f"{format_compact(budget.limit.cents, currency)}"
        )
    return f"{budget.spent.format()} de {budget.limit.format()}"


def usage_text(budget: Budget) -> str:
    """ "65 % usado · $ 260.000,00 de $ 400.000,00"."""
    return f"{used_percent_label(budget.used)} usado · {spent_of_limit(budget)}"


def remaining_text(budget: Budget) -> str:
    """ "Quedan $ 140.000,00", or "Excedido en $ 20.900,00" past the limit."""
    if budget.state is BudgetState.OVER:
        return f"Excedido en {(-budget.remaining).format()}"
    return f"Quedan {budget.remaining.format()}"


def budget_pill(budget: Budget) -> QLabel:
    """What is left, in a pill colored like the budget's bar."""
    pill = QLabel(remaining_text(budget))
    pill.setObjectName("ChangeBadge")
    set_style_property(pill, "tone", STATE_TONES[budget.state])
    return pill


def paint_progress(
    painter: QPainter, track: QRectF, fraction: float, color: str, track_color: str
) -> None:
    """A rounded track with its first ``fraction`` (0 to 1) filled in ``color``; any fill
    is at least a dot, so a start shows."""
    radius = track.height() / 2
    painter.setBrush(QColor(track_color))
    painter.drawRoundedRect(track, radius, radius)
    if fraction > 0:
        width = max(track.width() * fraction, track.height())
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(
            QRectF(track.left(), track.top(), width, track.height()), radius, radius
        )


class BudgetBar(AnimatedChart):
    """The spent part of the limit fills the bar in the budget's state color.

    Over the limit the whole bar turns pale red and the stretch past the limit, at the
    end, is solid red, so the size of the excess reads at a glance. In the current month a
    thin mark shows how far spending should have got by today.
    """

    HEIGHT = ControlSize.PROGRESS_HEIGHT
    MARK_OVERHANG = 3  # geometry: the mark of today, above and below the bar

    def __init__(self, theme: Theme, budget: Budget, parent: QWidget | None = None) -> None:
        super().__init__(theme, parent)
        self.budget = budget
        self.setFixedHeight(self.HEIGHT + 2 * self.MARK_OVERHANG)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(False)
        if self.shows_pace:
            self.setToolTip(f"Ritmo del mes: {round(budget.elapsed * 100)} %")
        self._start_transition()

    @property
    def shows_pace(self) -> bool:
        return 0 < self.budget.elapsed < 1

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = QRectF(0, self.MARK_OVERHANG, self.width(), self.HEIGHT)
        radius = self.HEIGHT / 2
        used = lerp(0.0, self.budget.used, self.progress)
        color = state_color(self._theme, self.budget.state)
        if used > 1:
            painter.setBrush(with_alpha(self._theme.expense, Opacity.OVER))
            painter.drawRoundedRect(track, radius, radius)
            excess = track.width() * (used - 1) / used
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(
                QRectF(track.right() - excess, track.top(), excess, track.height()), radius, radius
            )
        else:
            paint_progress(painter, track, used, color, self._theme.border)
        if self.shows_pace:
            x = track.left() + track.width() * self.budget.elapsed
            painter.setPen(QPen(QColor(self._theme.text_muted), Line.THICK))
            painter.drawLine(int(x), 0, int(x), self.height())
        painter.end()
