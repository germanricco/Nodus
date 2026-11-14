"""The page about one savings goal: its figures, how it grew month by month and what each
of its accounts adds to it."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.models.goal import Goal, GoalProgress, GoalState
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.services.container import Services
from nodus.services.errors import NotFoundError
from nodus.services.goal_service import GoalContribution
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId
from nodus.ui.pages.dashboard_cards import FigureTile, muted_label
from nodus.ui.pages.detail_page import DetailPage
from nodus.ui.pages.goals_page import delete_goal
from nodus.ui.theme.design import Chart, Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.chart_base import format_compact
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.goal_bar import amount_text, goal_pill, goal_sentence, month_phrase
from nodus.ui.widgets.line_chart import LineChart, LinePoint
from nodus.ui.widgets.row_actions import MoreButton, RowAction
from nodus.ui.widgets.style import clear_layout, make_hoverable

HISTORY_MONTHS = 12


def month_change_text(change: Money | None, hidden: bool) -> str:
    """ "+US$ 50,00 este mes", "-US$ 50,00 este mes" or "Sin cambios este mes": short,
    so five figures fit side by side."""
    if change is None:
        return ""
    if change.is_zero:
        return "Sin cambios este mes"
    sign = "-" if change.is_negative else "+"
    size = -change if change.is_negative else change
    return f"{sign}{amount_text(size, hidden)} este mes"


class ContributionRow(QWidget):
    """An account of the goal: its share of its balance and what that adds; a click
    opens the account."""

    clicked = Signal()

    def __init__(self, contribution: GoalContribution, hidden: bool) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(contribution.account.name)
        name.setObjectName("RowTitle")
        balance = amount_text(contribution.balance, hidden)
        texts.addWidget(name)
        texts.addWidget(muted_label(f"{contribution.percent} % de {balance}"))
        layout.addLayout(texts, stretch=1)
        counted = contribution.counted
        self.counted_label = QLabel("—" if counted is None else amount_text(counted, hidden))
        self.counted_label.setObjectName("RowAmount")
        layout.addWidget(self.counted_label)
        make_hoverable(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Abrir la cuenta")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()


class GoalDetailPage(DetailPage):
    """A goal at a glance: target, saved (with this month's change), what is missing,
    what it takes a month and the user's pace; the sentence of its state; what it had at
    each month end against the target; and its accounts.

    ``today`` is fixed by tests; otherwise the real date is used.
    """

    account_requested = Signal(int)  # account id

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(DetailId.GOAL, theme_manager)
        self._services = services
        self._event_bus = event_bus
        self._hidden = services.settings.amounts_hidden()
        self.goal: Goal | None = None
        self.today: date | None = None

        self.edit_button = self.add_header_button("Editar")
        self.edit_button.clicked.connect(self.edit)
        self.more_button = MoreButton(self.more_actions)
        self.add_header_widget(self.more_button)

        self.figures = FigureRow()
        self.target_label, self.target_note = QLabel(), muted_label("")
        self.saved_label, self.change_note = QLabel(), muted_label("")
        self.remaining_label = QLabel()
        self.needed_label = QLabel()
        self.pace_label, self.pace_note = QLabel(), muted_label("")
        for tile in (
            FigureTile("Objetivo", self.target_label, self.target_note, large=True),
            FigureTile("Ahorrado", self.saved_label, self.change_note, large=True),
            FigureTile("Falta", self.remaining_label, large=True),
            FigureTile("Por mes", self.needed_label, large=True),
            FigureTile("Ritmo por mes", self.pace_label, self.pace_note, large=True),
        ):
            self.figures.add_tile(tile)
        self.content_layout.addWidget(self.figures)

        self._status = QHBoxLayout()
        self._status.setSpacing(Space.S)
        self.content_layout.addLayout(self._status)
        self.pill: QLabel | None = None
        self.sentence_label = muted_label("")
        self.sentence_label.setWordWrap(True)

        chart_card = Card("Lo ahorrado en el tiempo")
        self.chart = LineChart(
            theme_manager.theme, self._format_value, self._format_axis, self._format_day
        )
        self.chart.setFixedHeight(Chart.ACCOUNT_HEIGHT)
        chart_card.body.addWidget(self.chart)
        theme_manager.theme_changed.connect(self.chart.set_theme)
        self.content_layout.addWidget(chart_card)

        self.accounts_card = Card("Cuentas")
        self._account_rows = QVBoxLayout()
        self._account_rows.setSpacing(0)
        self.accounts_card.body.addLayout(self._account_rows)
        self.content_layout.addWidget(self.accounts_card)
        self.content_layout.addStretch(1)  # the cards keep their height; the rest is blank
        self.account_rows: list[ContributionRow] = []

        for signal in (
            event_bus.goals_changed,
            event_bus.accounts_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self._data_changed)
        event_bus.amounts_hidden_changed.connect(self._set_amounts_hidden)

    def refresh(self) -> None:
        if self.item_id is None:
            return
        try:
            goal = self.goal = self._services.goals.get(self.item_id)
        except NotFoundError:
            self.back_requested.emit()
            return
        today = self.today or date.today()
        progress = self._services.goals.progress(goal, today)
        self.title_label.setText(goal.name)
        self._show_figures(goal, progress)
        self._show_status(goal, progress)
        points = [
            LinePoint(day, saved.cents)
            for day, saved in self._services.goals.month_ends(goal, today, HISTORY_MONTHS)
        ]
        if progress.saved is not None:
            points.append(LinePoint(today, progress.saved.cents))
        self.chart.set_reference(goal.target.cents)
        self.chart.set_points(points)
        self._show_accounts(self._services.goals.contributions(goal, today))

    # Actions

    def more_actions(self) -> list[RowAction]:
        goal = self.goal
        if goal is None:
            return []
        return [
            RowAction(
                "Desarchivar" if goal.is_archived else "Archivar", self.toggle_archived, "archive"
            ),
            RowAction("Eliminar", self.delete, "trash", destructive=True),
        ]

    def edit(self) -> None:
        GoalDialog(
            self._services, self._event_bus, self.goal, today=self.today, parent=self.window()
        ).exec()

    def toggle_archived(self) -> None:
        self._services.goals.set_archived(self.goal.id, not self.goal.is_archived)
        self._event_bus.goals_changed.emit()

    def delete(self) -> None:
        if delete_goal(self.window(), self._services, self._event_bus, self.goal):
            self.back_requested.emit()

    # Building

    def _show_figures(self, goal: Goal, progress: GoalProgress) -> None:
        hidden = self._hidden

        def shown(money: Money | None) -> str:
            return "—" if money is None else amount_text(money, hidden)

        self.target_label.setText(shown(goal.target))
        self.target_note.setText(
            f"para {month_phrase(Month.of(goal.target_date))}" if goal.target_date else "Sin fecha"
        )
        self.saved_label.setText(shown(progress.saved))
        self.change_note.setText(month_change_text(progress.month_change, hidden))
        self.remaining_label.setText(shown(progress.remaining))
        self.needed_label.setText(shown(progress.needed_per_month))
        if progress.pace_per_month is None:
            self.pace_label.setText("Falta historia")
            self.pace_note.setText("")
        else:
            self.pace_label.setText(f"≈ {shown(progress.pace_per_month)}")
            self.pace_note.setText(f"llega en {month_phrase(progress.eta)}" if progress.eta else "")
        self.figures.relayout()

    def _show_status(self, goal: Goal, progress: GoalProgress) -> None:
        clear_layout(self._status)
        self.sentence_label = muted_label(goal_sentence(goal, progress, self._hidden))
        self.sentence_label.setWordWrap(True)
        self.pill = goal_pill(progress)
        self._status.addWidget(self.pill)
        self._status.addWidget(self.sentence_label, stretch=1)
        if progress.state is GoalState.NO_RATE:
            self.pill.setToolTip("Cárgala en Ajustes")

    def _show_accounts(self, contributions: list[GoalContribution]) -> None:
        clear_layout(self._account_rows)
        self.account_rows = []
        for contribution in contributions:
            row = ContributionRow(contribution, self._hidden)
            account_id = contribution.account.id
            row.clicked.connect(lambda i=account_id: self.account_requested.emit(i))
            self._account_rows.addWidget(row)
            self.account_rows.append(row)

    def _data_changed(self) -> None:
        # Hidden, it is refreshed when shown again.
        if self.isVisible():
            self.refresh()

    def _set_amounts_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self._data_changed()

    def _format_value(self, cents: float) -> str:
        currency = self.goal.currency if self.goal else None
        if currency is None:
            return ""
        return amount_text(Money(round(cents), currency), self._hidden)

    def _format_axis(self, cents: float) -> str:
        if self._hidden or self.goal is None:
            return ""
        return format_compact(cents, self.goal.currency)

    def _format_day(self, day: date) -> str:
        return Month.of(day).short_name
