"""The page about one savings goal: its figures, how it grew month by month and what each
of its accounts adds to it."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from nodus.i18n import _
from nodus.models.goal import Goal, GoalProgress, GoalState
from nodus.models.language_format import format_percent
from nodus.models.money import Money
from nodus.models.period import Month, format_month_in_sentence
from nodus.services.container import Services
from nodus.services.errors import NotFoundError
from nodus.services.planning.goal_service import GoalContribution
from nodus.ui.actions.goals import delete_goal, toggle_goal_archived
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, RecordLink
from nodus.ui.pages.base.detail_page import DetailPage
from nodus.ui.theme.design import Chart, RowRole, Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.charts.goal_bar import goal_pill, goal_sentence
from nodus.ui.widgets.charts.line_chart import LineChart, LinePoint, money_formats
from nodus.ui.widgets.figure_row import FigureRow
from nodus.ui.widgets.figure_tile import FigureTile
from nodus.ui.widgets.hero_figure import HeroFigure
from nodus.ui.widgets.money_label import amount_text, month_change_text
from nodus.ui.widgets.style import clear_layout, make_hoverable, muted_label
from nodus.ui.widgets.tables.row_actions import Effect, MoreButton, RowAction, open_cue
from nodus.ui.widgets.tables.row_layout import (
    row_detail,
    row_layout,
    row_lines,
    row_list,
    row_title,
)

HISTORY_MONTHS = 12


class ContributionRow(QWidget):
    """An account of the goal: its share of its balance and what that adds; a click
    opens the account."""

    clicked = Signal()

    def __init__(self, contribution: GoalContribution, hidden: bool) -> None:
        super().__init__()
        layout = row_layout(self, RowRole.DOUBLE)
        texts = row_lines()
        name = row_title(contribution.account.name)
        balance = amount_text(contribution.balance, hidden)
        texts.addWidget(name)
        texts.addWidget(
            row_detail(
                _("{percent} de {balance}").format(
                    percent=format_percent(contribution.percent), balance=balance
                )
            )
        )
        layout.addLayout(texts, stretch=1)
        counted = contribution.counted
        self.counted_label = QLabel("—" if counted is None else amount_text(counted, hidden))
        self.counted_label.setObjectName("RowAmount")
        layout.addWidget(self.counted_label)
        layout.addWidget(open_cue())
        make_hoverable(self)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(DetailId.ACCOUNT.open_text)

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

    record_requested = Signal(object)  # RecordLink

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(DetailId.GOAL, theme_manager)
        self._services = services
        self._event_bus = event_bus
        self._hidden = services.settings.amounts_hidden()
        self.goal: Goal | None = None
        self.today: date | None = None

        self.edit_button = self.add_header_button(_("Editar"))
        self.edit_button.clicked.connect(self.edit)
        self.more_button = MoreButton(self.more_actions)
        self.add_header_widget(self.more_button)

        self.figures = FigureRow()
        self.target_label, self.target_note = QLabel(), muted_label("")
        self.saved_label, self.change_note = QLabel(), muted_label("")
        self.remaining_label = QLabel()
        self.needed_label = QLabel()
        self.pace_label, self.pace_note = QLabel(), muted_label("")
        # The page scrolls, as an account's: in a short window the cards keep their height.
        self.body = self.scrolling_body()
        self.body.addWidget(HeroFigure(_("Ahorrado"), self.saved_label, self.change_note))
        for tile in (
            FigureTile(_("Objetivo"), self.target_label, self.target_note),
            FigureTile(_("Falta"), self.remaining_label),
            FigureTile(_("Por mes"), self.needed_label),
            FigureTile(_("Ritmo por mes"), self.pace_label, self.pace_note),
        ):
            self.figures.add_tile(tile)
        self.body.addWidget(self.figures)

        self._status = QHBoxLayout()
        self._status.setSpacing(Space.S)
        self.body.addLayout(self._status)
        self.pill: QLabel | None = None

        chart_card = Card(_("Lo ahorrado en el tiempo"))
        self.chart = LineChart(
            theme_manager.theme,
            *money_formats(lambda: self.goal.currency if self.goal else None, lambda: self._hidden),
        )
        self.chart.setFixedHeight(Chart.DETAIL_HEIGHT)
        chart_card.body.addWidget(self.chart)
        theme_manager.theme_changed.connect(self.chart.set_theme)
        self.body.addWidget(chart_card)

        self.accounts_card = Card(_("Cuentas"))
        self._account_rows = row_list()
        self.accounts_card.body.addLayout(self._account_rows)
        self.body.addWidget(self.accounts_card)
        self.body.addStretch(1)  # the cards keep their height; the rest is blank
        self.account_rows: list[ContributionRow] = []

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
        self.set_title(goal.name)
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
                _("Desarchivar") if goal.is_archived else _("Archivar"),
                self.toggle_archived,
                "archive",
                effect=Effect.TOGGLE,
            ),
            RowAction(
                _("Eliminar"), self.delete, "trash", destructive=True, effect=Effect.CONFIRMED
            ),
        ]

    def edit(self) -> None:
        GoalDialog(
            self._services, self._event_bus, self.goal, today=self.today, parent=self.window()
        ).exec()

    def toggle_archived(self) -> None:
        toggle_goal_archived(self._services, self._event_bus, self.goal)

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
            _("para {month}").format(month=format_month_in_sentence(Month.of(goal.target_date)))
            if goal.target_date
            else _("Sin fecha")
        )
        self.saved_label.setText(shown(progress.saved))
        self.change_note.setText(month_change_text(progress.month_change, hidden))
        self.remaining_label.setText(shown(progress.remaining))
        self.needed_label.setText(shown(progress.needed_per_month))
        if progress.pace_per_month is None:
            self.pace_label.setText(_("Falta historia"))
            self.pace_note.setText("")
        else:
            self.pace_label.setText(f"≈ {shown(progress.pace_per_month)}")
            self.pace_note.setText(
                _("llega en {month}").format(month=format_month_in_sentence(progress.eta))
                if progress.eta
                else ""
            )
        self.figures.relayout()

    def _show_status(self, goal: Goal, progress: GoalProgress) -> None:
        clear_layout(self._status)
        self.sentence_label = muted_label(goal_sentence(goal, progress, self._hidden))
        self.sentence_label.setWordWrap(True)
        self.pill = goal_pill(progress)
        self._status.addWidget(self.pill)
        self._status.addWidget(self.sentence_label, stretch=1)
        if progress.state is GoalState.NO_RATE:
            self.pill.setToolTip(_("Cárgala en Ajustes"))

    def _show_accounts(self, contributions: list[GoalContribution]) -> None:
        clear_layout(self._account_rows)
        self.account_rows = []
        for contribution in contributions:
            row = ContributionRow(contribution, self._hidden)
            account_id = contribution.account.id
            row.clicked.connect(
                lambda i=account_id: self.record_requested.emit(RecordLink.account(i))
            )
            self._account_rows.addWidget(row)
            self.account_rows.append(row)

    def _set_amounts_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        self.request_refresh()
