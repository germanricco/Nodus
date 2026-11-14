"""How a savings goal is drawn and told: its progress bar, its state pill and the sentence
that says where it stands and what to do. The goals page and a goal's detail share them."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from nodus.models.goal import Goal, GoalProgress, GoalState
from nodus.models.money import Money
from nodus.models.period import MONTH_NAMES, Month, format_date
from nodus.ui.theme.design import ControlSize
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.budget_bar import paint_progress
from nodus.ui.widgets.chart_base import AnimatedChart, lerp
from nodus.ui.widgets.money_label import amount_text
from nodus.ui.widgets.style import set_style_property

# The pill of each state, and its tone (the colors of ``ChangeBadge``).
STATE_LABELS = {
    GoalState.REACHED: ("Alcanzada", "good"),
    GoalState.ON_TRACK: ("Al día", "good"),
    GoalState.BEHIND: ("Atrasada", "warning"),
    GoalState.OVERDUE: ("Vencida", "bad"),
    GoalState.NO_HISTORY: ("Sin historia", "neutral"),
    GoalState.NO_DATE: ("Sin fecha", "neutral"),
    GoalState.NO_RATE: ("Sin cotización", "neutral"),
}
NO_RATE_TEXT = "Falta la cotización para sumar las cuentas en otras monedas."


def month_phrase(month: Month) -> str:
    """ "febrero de 2027", as it reads inside a sentence."""
    return f"{MONTH_NAMES[month.month - 1].lower()} de {month.year}"


def saved_of_target(progress: GoalProgress, hidden: bool) -> str:
    """ "US$ 820,00 de US$ 2.000,00 · 41 %"; without a rate, "— de US$ 2.000,00"."""
    target = amount_text(progress.target, hidden)
    if progress.saved is None:
        return f"— de {target}"
    return f"{amount_text(progress.saved, hidden)} de {target} · {progress.percent} %"


def goal_sentence(goal: Goal, progress: GoalProgress, hidden: bool = False) -> str:
    """Where the goal stands, in one sentence, and what to do when it falls behind."""
    state = progress.state

    def amount(money: Money | None) -> str:
        assert money is not None  # every state that names an amount has it
        return amount_text(money, hidden)

    needed = (
        f" Para llegar a tiempo hacen falta {amount(progress.needed_per_month)} por mes."
        if progress.needed_per_month is not None
        else ""
    )
    if state is GoalState.REACHED:
        return f"Alcanzada el {format_date(goal.reached_on)}." if goal.reached_on else "Alcanzada."
    if state is GoalState.NO_RATE:
        return NO_RATE_TEXT
    if state is GoalState.OVERDUE:
        missing = amount(progress.remaining)
        return f"La fecha pasó y faltan {missing}. Cambia la fecha o el objetivo."
    if state is GoalState.NO_HISTORY:
        return "Todavía no hay 3 meses para medir tu ritmo." + needed
    if progress.eta is None:  # saving nothing, or less every month
        return "Tu ahorro no viene creciendo en los últimos meses." + needed
    arrives = f"A este ritmo llegas en {month_phrase(progress.eta)}"
    if state is GoalState.ON_TRACK:
        return f"Vas bien: {arrives[0].lower()}{arrives[1:]}."
    if state is GoalState.BEHIND:
        assert goal.target_date is not None  # behind means behind its date
        due = Month.of(goal.target_date)
        late = (progress.eta.year - due.year) * 12 + progress.eta.month - due.month
        return f"{arrives}, {late} {'mes' if late == 1 else 'meses'} tarde." + needed
    return f"{arrives}."


def goal_pill(progress: GoalProgress) -> QLabel:
    """The goal's state in a pill: green, amber, red or gray."""
    text, tone = STATE_LABELS[progress.state]
    pill = QLabel(text)
    pill.setObjectName("ChangeBadge")
    set_style_property(pill, "tone", tone)
    return pill


def bar_color(theme: Theme, state: GoalState) -> str:
    """Green on track or reached, amber behind, red overdue; the accent otherwise."""
    return {
        GoalState.REACHED: theme.income,
        GoalState.ON_TRACK: theme.income,
        GoalState.BEHIND: theme.warning,
        GoalState.OVERDUE: theme.expense,
    }.get(state, theme.accent)


class GoalBar(AnimatedChart):
    """The saved part of the target fills the bar, in the color of the goal's state; past
    the target it stays full."""

    HEIGHT = ControlSize.PROGRESS_HEIGHT

    def __init__(self, theme: Theme, progress: GoalProgress, parent: QWidget | None = None) -> None:
        super().__init__(theme, parent)
        self.goal_progress = progress
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(False)
        self._start_transition()

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
            lerp(0.0, self.fraction, self.progress),
            bar_color(self._theme, self.goal_progress.state),
            self._theme.border,
        )
        painter.end()
