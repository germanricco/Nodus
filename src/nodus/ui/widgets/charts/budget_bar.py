"""How a budget is drawn: its progress bar against the pace of the month, its pill and texts."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QLabel, QWidget

from nodus.i18n import _
from nodus.models.budget import Budget, BudgetState, used_percent_label
from nodus.models.language_format import format_percent
from nodus.ui.theme.design import ControlSize, Line, Opacity
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.change_badge import Tone, status_pill
from nodus.ui.widgets.charts.chart_base import ProgressStrip, format_compact, with_alpha

STATE_TONES = {
    BudgetState.ON_TRACK: Tone.GOOD,
    BudgetState.AHEAD: Tone.WARNING,
    BudgetState.OVER: Tone.BAD,
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
        spent = format_compact(budget.spent.cents, currency)
        limit = format_compact(budget.limit.cents, currency)
    else:
        spent, limit = budget.spent.format(), budget.limit.format()
    return _("{spent} de {limit}").format(spent=spent, limit=limit)


def usage_text(budget: Budget) -> str:
    """ "65 % usado · $ 260.000,00 de $ 400.000,00"."""
    return _("{percent} usado · {spent_of_limit}").format(
        percent=used_percent_label(budget.used), spent_of_limit=spent_of_limit(budget)
    )


def remaining_text(budget: Budget) -> str:
    """ "Quedan $ 140.000,00", or "Excedido en $ 20.900,00" past the limit."""
    if budget.state is BudgetState.OVER:
        return _("Excedido en {amount}").format(amount=(-budget.remaining).format())
    return _("Quedan {amount}").format(amount=budget.remaining.format())


def budget_pill(budget: Budget) -> QLabel:
    """What is left, in a pill colored like the budget's bar."""
    return status_pill(remaining_text(budget), STATE_TONES[budget.state])


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


class BudgetBar(ProgressStrip):
    """The spent part of the limit fills the bar in the budget's state color.

    Over the limit the whole bar turns pale red and the stretch past the limit, at the
    end, is solid red, so the size of the excess reads at a glance. In the current month a
    thin mark shows how far spending should have got by today.
    """

    HEIGHT = ControlSize.PROGRESS_HEIGHT
    MARK_OVERHANG = 3  # geometry: the mark of today, above and below the bar

    def __init__(
        self,
        theme: Theme,
        budget: Budget,
        start: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(theme, self.HEIGHT + 2 * self.MARK_OVERHANG, start, parent)
        self.budget = budget
        if self.shows_pace:
            self.setToolTip(
                _("Ritmo del mes: {percent}").format(
                    percent=format_percent(round(budget.elapsed * 100))
                )
            )
        self._begin()

    @property
    def fraction(self) -> float:
        return self.budget.used

    @property
    def shows_pace(self) -> bool:
        return 0 < self.budget.elapsed < 1

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = QRectF(0, self.MARK_OVERHANG, self.width(), self.HEIGHT)
        radius = self.HEIGHT / 2
        used = self.shown_fraction
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
