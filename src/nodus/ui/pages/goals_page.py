"""Goals section: every savings goal, how far it got and whether the user's pace gets
there in time, in progress first, then reached, then archived."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus.models.account import Account
from nodus.models.goal import Goal, GoalProgress, GoalState
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.page import Page
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.empty_state import empty_page_card
from nodus.ui.widgets.goal_bar import GoalBar, goal_pill, goal_sentence, saved_of_target
from nodus.ui.widgets.row_actions import MoreButton, RowAction, install_row_actions
from nodus.ui.widgets.style import clear_layout, set_style_property

EMPTY_TITLE = "Todavía no hay metas"
EMPTY_TEXT = (
    "Una meta junta el saldo de tus cuentas de ahorro hacia un monto, con fecha si quieres. "
    "Nodus te dice cuánto apartar por mes y si a tu ritmo llegas a tiempo."
)
DELETE_TEXT = "Se elimina la meta «{name}». Las cuentas y sus movimientos no se tocan."


def accounts_text(services: Services, goal: Goal) -> str:
    """ "Ahorro USD (100 %)" for one account, "2 cuentas" for more."""
    if len(goal.shares) > 1:
        return f"{len(goal.shares)} cuentas"
    [share] = goal.shares
    return f"{services.accounts.get(share.account_id).name} ({share.percent} %)"


class GoalRow(QWidget):
    """One goal: its name and accounts, how much it has, its state, its bar and the
    sentence that says how it goes."""

    edit_requested = Signal(object)  # Goal
    archive_toggled = Signal(object)  # Goal
    delete_requested = Signal(object)  # Goal
    rate_requested = Signal()

    def __init__(
        self, goal: Goal, progress: GoalProgress, accounts: str, theme: Theme, hidden: bool
    ) -> None:
        super().__init__()
        self.goal = goal
        self.goal_progress = progress
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        layout.setSpacing(Space.XS)

        top = QHBoxLayout()
        top.setSpacing(Space.M)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(goal.name)
        name.setObjectName("RowTitle")
        detail = QLabel(accounts)
        set_style_property(detail, "muted", True)
        texts.addWidget(name)
        texts.addWidget(detail)
        top.addLayout(texts, stretch=1)
        self.figures_label = QLabel(saved_of_target(progress, hidden))
        set_style_property(self.figures_label, "muted", True)
        top.addWidget(self.figures_label)
        self.pill = goal_pill(progress)
        top.addWidget(self.pill)
        self.more_button = MoreButton(self.actions)
        top.addWidget(self.more_button)
        layout.addLayout(top)

        self.bar = GoalBar(theme, progress)
        layout.addWidget(self.bar)
        bottom = QHBoxLayout()
        self.sentence_label = QLabel(goal_sentence(goal, progress, hidden))
        self.sentence_label.setWordWrap(True)
        set_style_property(self.sentence_label, "muted", True)
        bottom.addWidget(self.sentence_label, stretch=1)
        if progress.state is GoalState.NO_RATE:
            self.rate_button = QPushButton("Cargar cotización")
            self.rate_button.setObjectName("SmallButton")
            self.rate_button.clicked.connect(self.rate_requested)
            bottom.addWidget(self.rate_button)
        layout.addLayout(bottom)

        install_row_actions(self, self.actions)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Editar la meta")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.edit_requested.emit(self.goal)

    def actions(self) -> list[RowAction]:
        goal = self.goal
        return [
            RowAction("Editar", lambda: self.edit_requested.emit(goal), "pencil", default=True),
            RowAction(
                "Desarchivar" if goal.is_archived else "Archivar",
                lambda: self.archive_toggled.emit(goal),
                "archive",
            ),
            RowAction(
                "Eliminar", lambda: self.delete_requested.emit(goal), "trash", destructive=True
            ),
        ]


class GoalsPage(Page):
    """The goals, grouped by where they stand. Nothing here moves money: a goal only
    looks at the balances of its accounts."""

    navigate_requested = Signal(object)  # PageId

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Metas")
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self._today: date | None = None
        self.create_button = self.add_header_button("Agregar meta", primary=True)
        self.create_button.clicked.connect(lambda: self.open_goal_dialog())

        container = QWidget()
        self._sections = QVBoxLayout(container)
        self._sections.setContentsMargins(0, 0, 0, 0)
        self._sections.setSpacing(Space.L)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)
        self.rows: list[GoalRow] = []
        self.section_titles: list[str] = []

        theme_manager.theme_changed.connect(lambda _theme: self.refresh(self._today))
        for signal in (
            event_bus.goals_changed,
            event_bus.accounts_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
            event_bus.amounts_hidden_changed,
        ):
            signal.connect(lambda *_args: self.refresh(self._today))

    def refresh(self, today: date | None = None) -> None:
        """``today`` is fixed by tests; otherwise the real date is used."""
        self._today = today
        today = today or date.today()
        clear_layout(self._sections)
        self.rows, self.section_titles = [], []
        goals = self._services.goals.list_goals()
        if not goals:
            card, _state = empty_page_card(
                EMPTY_TITLE, EMPTY_TEXT, "Agregar meta", self.open_goal_dialog
            )
            self._sections.addWidget(card)
            self._sections.addStretch()
            return
        progress = {goal.id: self._services.goals.progress(goal, today) for goal in goals}
        active = [g for g in goals if not g.is_archived]
        reached = [g for g in active if progress[g.id].state is GoalState.REACHED]
        sections = (
            ("En curso", [g for g in active if g not in reached]),
            ("Alcanzadas", reached),
            ("Archivadas", [g for g in goals if g.is_archived]),
        )
        for title, section in sections:
            if section:
                self._sections.addWidget(self._section_card(title, section, progress))
        self._sections.addStretch()

    # Actions

    def open_goal_dialog(self, goal: Goal | None = None, account: Account | None = None) -> None:
        GoalDialog(
            self._services, self._event_bus, goal, account, self._today, parent=self.window()
        ).exec()

    def toggle_archived(self, goal: Goal) -> None:
        self._services.goals.set_archived(goal.id, not goal.is_archived)
        self._event_bus.goals_changed.emit()

    def delete_goal(self, goal: Goal) -> None:
        if not confirm(self.window(), "Eliminar meta", DELETE_TEXT.format(name=goal.name)):
            return
        self._services.goals.delete(goal.id)
        self._event_bus.goals_changed.emit()

    # Building

    def _section_card(
        self, title: str, goals: list[Goal], progress: dict[int | None, GoalProgress]
    ) -> Card:
        card = Card(f"{title} ({len(goals)})")
        self.section_titles.append(title)
        theme = self._theme_manager.theme
        hidden = self._services.settings.amounts_hidden()
        for goal in goals:
            row = GoalRow(
                goal, progress[goal.id], accounts_text(self._services, goal), theme, hidden
            )
            row.edit_requested.connect(self.open_goal_dialog)
            row.archive_toggled.connect(self.toggle_archived)
            row.delete_requested.connect(self.delete_goal)
            row.rate_requested.connect(lambda: self.navigate_requested.emit(PageId.SETTINGS))
            card.body.addWidget(row)
            self.rows.append(row)
        return card
