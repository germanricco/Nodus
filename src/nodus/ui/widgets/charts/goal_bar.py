"""How a savings goal is drawn and told: its progress bar, its state pill and the sentence
that says where it stands and what to do. The goals page and a goal's detail share them."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QWidget

from nodus.i18n import N_, _, ngettext
from nodus.models.goal import Goal, GoalProgress, GoalState
from nodus.models.language_format import format_percent
from nodus.models.money import Money
from nodus.models.period import Month, format_date, format_month_in_sentence
from nodus.ui.text.labels import NO_RATE_TEXT
from nodus.ui.theme.design import ControlSize
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.change_badge import Tone, status_pill
from nodus.ui.widgets.charts.budget_bar import paint_progress
from nodus.ui.widgets.charts.chart_base import ProgressStrip
from nodus.ui.widgets.money_label import amount_text

# The pill of each state, and its tone (the colors of ``ChangeBadge``).
STATE_LABELS = {
    GoalState.REACHED: (N_("Alcanzada"), Tone.GOOD),
    GoalState.ON_TRACK: (N_("Al día"), Tone.GOOD),
    GoalState.BEHIND: (N_("Atrasada"), Tone.WARNING),
    GoalState.OVERDUE: (N_("Vencida"), Tone.BAD),
    GoalState.NO_HISTORY: (N_("Sin historia"), Tone.NEUTRAL),
    GoalState.NO_DATE: (N_("Sin fecha"), Tone.NEUTRAL),
    GoalState.NO_RATE: (NO_RATE_TEXT, Tone.NEUTRAL),
}
MISSING_RATE_SENTENCE = N_("Falta la cotización para sumar las cuentas en otras monedas.")


def saved_of_target(progress: GoalProgress, hidden: bool) -> str:
    """ "US$ 820,00 de US$ 2.000,00 · 41 %"; without a rate, "— de US$ 2.000,00"."""
    target = amount_text(progress.target, hidden)
    if progress.saved is None:
        return _("— de {target}").format(target=target)
    percent = format_percent(progress.percent)
    return _("{saved} de {target} · {percent}").format(
        saved=amount_text(progress.saved, hidden), target=target, percent=percent
    )


def goal_sentence(goal: Goal, progress: GoalProgress, hidden: bool = False) -> str:
    """Where the goal stands, in one sentence, and what to do when it falls behind."""
    state = progress.state

    def amount(money: Money | None) -> str:
        assert money is not None  # every state that names an amount has it
        return amount_text(money, hidden)

    needed = (
        " "
        + _("Para llegar a tiempo hacen falta {amount} por mes.").format(
            amount=amount(progress.needed_per_month)
        )
        if progress.needed_per_month is not None
        else ""
    )
    if state is GoalState.REACHED:
        if goal.reached_on:
            return _("Alcanzada el {date}.").format(date=format_date(goal.reached_on))
        return _("Alcanzada.")
    if state is GoalState.NO_RATE:
        return _(MISSING_RATE_SENTENCE)
    if state is GoalState.OVERDUE:
        missing = amount(progress.remaining)
        return _("La fecha pasó y faltan {amount}. Cambia la fecha o el objetivo.").format(
            amount=missing
        )
    if state is GoalState.NO_HISTORY:
        return _("Todavía no hay 3 meses para medir tu ritmo.") + needed
    if progress.eta is None:  # saving nothing, or less every month
        return _("Tu ahorro no viene creciendo en los últimos meses.") + needed
    month = format_month_in_sentence(progress.eta)
    if state is GoalState.ON_TRACK:
        return _("Vas bien: a este ritmo llegas en {month}.").format(month=month)
    if state is GoalState.BEHIND:
        assert goal.target_date is not None  # behind means behind its date
        late = Month.of(goal.target_date).months_to(progress.eta)
        late_text = ngettext(
            "A este ritmo llegas en {month}, {count} mes tarde.",
            "A este ritmo llegas en {month}, {count} meses tarde.",
            late,
        ).format(month=month, count=late)
        return late_text + needed
    return _("A este ritmo llegas en {month}.").format(month=month)


def goal_pill(progress: GoalProgress) -> QLabel:
    """The goal's state in a pill: green, amber, red or gray."""
    text, tone = STATE_LABELS[progress.state]
    return status_pill(_(text), tone)


def bar_color(theme: Theme, state: GoalState) -> str:
    """Green on track or reached, amber behind, red overdue; the accent otherwise."""
    return {
        GoalState.REACHED: theme.income,
        GoalState.ON_TRACK: theme.income,
        GoalState.BEHIND: theme.warning,
        GoalState.OVERDUE: theme.expense,
    }.get(state, theme.accent)


class GoalBar(ProgressStrip):
    """The saved part of the target fills the bar, in the color of the goal's state; past
    the target it stays full."""

    HEIGHT = ControlSize.PROGRESS_HEIGHT

    def __init__(
        self,
        theme: Theme,
        progress: GoalProgress,
        start: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(theme, self.HEIGHT, start, parent)
        self.goal_progress = progress
        self._begin()

    @property
    def fraction(self) -> float:
        return min(1.0, self.goal_progress.percent / 100)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        paint_progress(
            painter,
            QRectF(0, 0, self.width(), self.HEIGHT),
            self.shown_fraction,
            bar_color(self._theme, self.goal_progress.state),
            self._theme.border,
        )
        painter.end()
