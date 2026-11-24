"""Goals section: every savings goal, how far it got and whether the user's pace gets
there in time, in progress first, then reached, then archived."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from nodus.i18n import N_, _, ngettext
from nodus.models.account import Account
from nodus.models.goal import Goal, GoalProgress, GoalState, attention_key
from nodus.models.language_format import format_percent
from nodus.models.period import Month, format_month_in_sentence
from nodus.services.container import Services
from nodus.ui.actions.goals import delete_goal, toggle_goal_archived
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages.base.page import Page
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.archived_section import ArchivedSection
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.card_grid import CardGrid
from nodus.ui.widgets.charts.chart_base import shown_fractions
from nodus.ui.widgets.charts.goal_bar import GoalBar, goal_pill, goal_sentence
from nodus.ui.widgets.elided_label import ElidedLabel
from nodus.ui.widgets.empty_state import empty_page_card
from nodus.ui.widgets.money_label import amount_text
from nodus.ui.widgets.style import clear_layout, muted_label
from nodus.ui.widgets.tables.row_actions import (
    Effect,
    MoreButton,
    RowAction,
    install_row_actions,
    open_cue,
)

# Where the fold of the archived goals is saved (``SettingsService.archive_folded``).
ARCHIVE = "goals"
EMPTY_TITLE = N_("Todavía no hay metas")
EMPTY_TEXT = N_(
    "Una meta junta el saldo de tus cuentas de ahorro hacia un monto, con fecha si quieres. "
    "Nodus te dice cuánto apartar por mes y si a tu ritmo llegas a tiempo."
)


def accounts_text(services: Services, goal: Goal) -> str:
    """ "Ahorro USD (100 %)" for one account, "2 cuentas" for more."""
    if len(goal.shares) > 1:
        count = len(goal.shares)
        return ngettext("{count} cuenta", "{count} cuentas", count).format(count=count)
    [share] = goal.shares
    return f"{services.accounts.get(share.account_id).name} ({format_percent(share.percent)})"


def context_text(services: Services, goal: Goal) -> str:
    """ "Ahorro USD (100 %) · para octubre de 2027": where the goal saves, and by when."""
    accounts = accounts_text(services, goal)
    if goal.target_date is None:
        return accounts
    when = _("para {month}").format(month=format_month_in_sentence(Month.of(goal.target_date)))
    return f"{accounts} · {when}"


class GoalCard(Card):
    """One goal as a card of the grid, in the order every card follows (plan 029a, 5.1):
    its name, state and menu; its accounts and date; how much it has against its target;
    its bar; and the sentence that says how it goes. A click anywhere opens its page."""

    detail_requested = Signal(object)  # Goal
    edit_requested = Signal(object)  # Goal
    archive_toggled = Signal(object)  # Goal
    delete_requested = Signal(object)  # Goal
    rate_requested = Signal()

    def __init__(
        self,
        goal: Goal,
        progress: GoalProgress,
        context: str,
        theme: Theme,
        hidden: bool,
        start: float | None = None,
    ) -> None:
        super().__init__()
        self.goal = goal

        top = QHBoxLayout()
        top.setSpacing(Space.S)
        name = ElidedLabel(goal.name)
        name.setObjectName("RowTitle")
        top.addWidget(name, stretch=1)
        self.pill = goal_pill(progress)
        top.addWidget(self.pill)
        self.more_button = MoreButton(self.actions)
        top.addWidget(self.more_button)
        top.addWidget(open_cue())
        self.body.addLayout(top)
        self.context_label = muted_label(context)
        self.body.addWidget(self.context_label)
        self.body.addSpacing(Space.XS)

        figure = QHBoxLayout()
        figure.setSpacing(Space.S)
        saved = "—" if progress.saved is None else amount_text(progress.saved, hidden)
        self.saved_label = QLabel(saved)
        self.saved_label.setObjectName("StatValueLarge")
        figure.addWidget(self.saved_label, alignment=Qt.AlignmentFlag.AlignBaseline)
        self.target_label = muted_label(
            _("de {amount}").format(amount=amount_text(progress.target, hidden))
        )
        figure.addWidget(self.target_label, alignment=Qt.AlignmentFlag.AlignBaseline)
        figure.addStretch()
        self.body.addLayout(figure)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(Space.S)
        self.bar = GoalBar(theme, progress, start)
        bar_row.addWidget(self.bar, stretch=1)
        self.percent_label = muted_label(
            "" if progress.saved is None else format_percent(progress.percent)
        )
        bar_row.addWidget(self.percent_label)
        self.body.addLayout(bar_row)

        bottom = QHBoxLayout()
        self.sentence_label = muted_label(goal_sentence(goal, progress, hidden))
        self.sentence_label.setWordWrap(True)
        bottom.addWidget(self.sentence_label, stretch=1)
        if progress.state is GoalState.NO_RATE:
            self.rate_button = QPushButton(_("Cargar cotización"))
            self.rate_button.setObjectName("SmallButton")
            self.rate_button.clicked.connect(self.rate_requested)
            bottom.addWidget(self.rate_button)
        self.body.addLayout(bottom)

        install_row_actions(self, self.actions, open_on_click=DetailId.GOAL.open_text)

    def actions(self) -> list[RowAction]:
        goal = self.goal
        return [
            RowAction(
                _("Abrir"),
                lambda: self.detail_requested.emit(goal),
                default=True,
                effect=Effect.OPEN,
            ),
            RowAction(
                _("Editar"), lambda: self.edit_requested.emit(goal), "pencil", effect=Effect.OPEN
            ),
            RowAction(
                _("Desarchivar") if goal.is_archived else _("Archivar"),
                lambda: self.archive_toggled.emit(goal),
                "archive",
                effect=Effect.TOGGLE,
            ),
            RowAction(
                _("Eliminar"),
                lambda: self.delete_requested.emit(goal),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]


class GoalsPage(Page):
    """The goals as cards, which suit few, different items looked at one by one (plan
    029a, 2). The ones followed share one grid, so they fill the width, in the order of
    the attention they ask for (``attention_key``): overdue and behind first, reached
    last, each with its pill. The archived go apart, in an ``ArchivedSection``. Nothing
    here moves money: a goal only looks at the balances of its accounts."""

    navigate_requested = Signal(object)  # PageId
    detail_requested = Signal(int)  # goal id

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.GOALS.label)
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self._today: date | None = None
        self.create_button = self.add_header_button(_("Agregar meta"), primary=True)
        self.create_button.clicked.connect(lambda: self.open_goal_dialog())

        self._sections = self.scrolling_body()
        self.cards: list[GoalCard] = []
        self._shown: dict[int | None, float] = {}  # each bar, where its next one starts
        self.archived: ArchivedSection | None = None

    def refresh(self, today: date | None = None) -> None:
        """``today`` is fixed by tests, and kept by later refreshes; otherwise the
        real date is used."""
        self._today = today = today or self._today
        today = today or date.today()
        self._shown = shown_fractions({card.goal.id: card.bar for card in self.cards})
        clear_layout(self._sections)
        self.cards = []
        self.archived = None
        goals = self._services.goals.list_goals()
        if not goals:
            card, _state = empty_page_card(
                _(EMPTY_TITLE), _(EMPTY_TEXT), _("Agregar meta"), self.open_goal_dialog
            )
            self._sections.addWidget(card)
            self._sections.addStretch()
            return
        progress = {goal.id: self._services.goals.progress(goal, today) for goal in goals}
        ordered = sorted(goals, key=lambda g: attention_key(g, progress[g.id].state))
        followed = [g for g in ordered if not g.is_archived]
        archived = [g for g in ordered if g.is_archived]
        if followed:
            self._sections.addWidget(self._grid(followed, progress))
        if archived:
            settings = self._services.settings
            self.archived = ArchivedSection(
                len(archived), self._grid(archived, progress), settings.archive_folded(ARCHIVE)
            )
            self.archived.fold_toggled.connect(
                lambda folded: settings.set_archive_folded(ARCHIVE, folded)
            )
            self._sections.addWidget(self.archived)
        self._sections.addStretch()

    # Actions

    def open_goal_dialog(self, goal: Goal | None = None, account: Account | None = None) -> None:
        GoalDialog(
            self._services, self._event_bus, goal, account, self._today, parent=self.window()
        ).exec()

    def toggle_archived(self, goal: Goal) -> None:
        toggle_goal_archived(self._services, self._event_bus, goal)

    def delete(self, goal: Goal) -> None:
        delete_goal(self.window(), self._services, self._event_bus, goal)

    # Building

    def _grid(self, goals: list[Goal], progress: dict[int | None, GoalProgress]) -> CardGrid:
        """``goals`` as cards, in a grid."""
        theme = self._theme_manager.theme
        hidden = self._services.settings.amounts_hidden()
        cards = []
        for goal in goals:
            card = GoalCard(
                goal,
                progress[goal.id],
                context_text(self._services, goal),
                theme,
                hidden,
                self._shown.get(goal.id),
            )
            card.detail_requested.connect(lambda goal: self.detail_requested.emit(goal.id))
            card.edit_requested.connect(self.open_goal_dialog)
            card.archive_toggled.connect(self.toggle_archived)
            card.delete_requested.connect(self.delete)
            card.rate_requested.connect(lambda: self.navigate_requested.emit(PageId.SETTINGS))
            cards.append(card)
        grid = CardGrid()
        grid.set_cards(cards)
        self.cards += cards
        return grid
