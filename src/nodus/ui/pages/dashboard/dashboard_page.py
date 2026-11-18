"""Inicio, the dashboard: how much there is, how the period went and where the money went."""

from __future__ import annotations

from datetime import date
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QWidget,
)

from nodus.i18n import _
from nodus.models.period import Month, Period
from nodus.models.recurring_charge import RecurringCharge
from nodus.services.container import Services
from nodus.ui.actions.recurring import pay_charge, skip_charge, toggle_seen
from nodus.ui.actions.transactions import delete_transactions, edit_transaction
from nodus.ui.dialogs.restore_copy import restore_copy
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.base.net_worth_card import NetWorthCard
from nodus.ui.pages.base.page import Page
from nodus.ui.pages.dashboard.budgets_card import BudgetsCard
from nodus.ui.pages.dashboard.cash_flow_card import CashFlowCard
from nodus.ui.pages.dashboard.comparison_card import ComparisonCard
from nodus.ui.pages.dashboard.expenses_card import ExpensesCard
from nodus.ui.pages.dashboard.latest_transactions_card import (
    LATEST_COUNT,
    LATEST_COUNT_BELOW_UPCOMING,
    LatestTransactionsCard,
)
from nodus.ui.pages.dashboard.upcoming_payments_card import UpcomingPaymentsCard
from nodus.ui.period_selector import PeriodSelector
from nodus.ui.shell import tour
from nodus.ui.shell.coach_marks import mark_target
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.style import muted_label, scrolling, secondary_button

# The columns of the wide grid; narrower, the cards take two.
GRID_COLUMNS = 6


class Shape(Enum):
    """How the cards are laid out, from the widest window to the narrowest."""

    WIDE = auto()  # six columns: two cards side by side in every row
    NARROW = auto()  # one card per row, but the top's side cards together
    STACKED = auto()  # one card per row


# A card's place in the grid: (card, row, column, rows spanned, columns spanned).
Placement = tuple[QWidget, int, int, int, int]


class DashboardPage(Page):
    """Net worth with its trend, the period's cash flow, expenses by category and against
    the previous period, and the latest movements. Without accounts it shows how to get
    started instead.

    The cards are built once. When data changes while the dashboard is on screen (a
    transaction saved from the top bar, for instance), they receive the new figures and
    their charts move to them; when it is hidden, it refreshes on being shown again.
    """

    navigate_requested = Signal(object)  # PageId
    transactions_requested = Signal(object)  # TransactionFocus
    budgets_requested = Signal(object)  # Month

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.DASHBOARD.label)
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self.period_selector = PeriodSelector()
        self.add_header_widget(self.period_selector)
        mark_target(self.period_selector, tour.PERIOD)

        self.net_worth_card = NetWorthCard(services, theme_manager)
        self.net_worth_card.set_amounts_hidden(services.settings.amounts_hidden())
        event_bus.amounts_hidden_changed.connect(self.net_worth_card.set_amounts_hidden)
        self.net_worth_card.currency_changed.connect(event_bus.net_worth_currency_changed)
        self.net_worth_card.rate_requested.connect(
            lambda: self.navigate_requested.emit(PageId.SETTINGS)
        )
        self.latest_card = LatestTransactionsCard(services, theme_manager)
        self.latest_card.edit_requested.connect(
            lambda item: edit_transaction(services, event_bus, theme_manager, item, self.window())
        )
        self.latest_card.delete_requested.connect(
            lambda item: delete_transactions(services, event_bus, [item], self.window())
        )
        self.latest_card.see_all_requested.connect(
            lambda: self.transactions_requested.emit(
                TransactionFocus(self.period_selector.period())
            )
        )
        self.upcoming_card = UpcomingPaymentsCard(services)
        self.upcoming_card.pay_requested.connect(self.open_pay_dialog)
        self.upcoming_card.skip_requested.connect(
            lambda charge: skip_charge(self, services, event_bus, charge)
        )
        self.upcoming_card.seen_toggled.connect(
            lambda charge: toggle_seen(self, services, event_bus, charge)
        )
        self.upcoming_card.see_all_requested.connect(
            lambda: self.navigate_requested.emit(PageId.RECURRING)
        )
        self.flow_card = CashFlowCard(theme_manager)
        self.budgets_card = BudgetsCard(services, theme_manager)
        self.budgets_card.category_clicked.connect(
            lambda category_id: self.transactions_requested.emit(
                TransactionFocus(Period.of_months(self._budgets_month()), category_id)
            )
        )
        self.budgets_card.see_all_requested.connect(
            lambda: self.budgets_requested.emit(self._budgets_month())
        )
        self.expenses_card = ExpensesCard(theme_manager)
        self.comparison_card = ComparisonCard()
        for card in (self.expenses_card, self.comparison_card):
            card.category_clicked.connect(
                lambda category_id: self.transactions_requested.emit(
                    TransactionFocus(self.period_selector.period(), category_id)
                )
            )

        grid_page = QWidget()
        self._grid = QGridLayout(grid_page)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(Space.L)
        self._layout: tuple[Shape, bool, bool] | None = None
        # Owned by the grid page from the start, so a card left out of the grid (upcoming
        # payments without charges) never becomes a window of its own when shown.
        for card in self._cards():
            card.setParent(grid_page)
        scroll = self._scroll = scrolling(grid_page, horizontal=False)
        # The cards follow the width they are shown in, which the scroll area learns
        # after the page does: arranging on the page's resize would read the old one.
        scroll.viewport().installEventFilter(self)

        self._stack = QStackedWidget()
        self._welcome = self._welcome_card()
        welcome_page = QWidget()
        welcome_layout = QGridLayout(welcome_page)
        welcome_layout.setContentsMargins(0, 0, 0, 0)
        welcome_layout.addWidget(self._welcome, 0, 0)
        welcome_layout.setRowStretch(1, 1)
        self._stack.addWidget(welcome_page)
        self._stack.addWidget(scroll)
        self.content_layout.addWidget(self._stack)

        self.period_selector.period_changed.connect(self.refresh)
        theme_manager.theme_changed.connect(self._remeasure)

    @property
    def see_all_button(self) -> QPushButton:
        return self.latest_card.see_all_button

    def refresh(self) -> None:
        if not self._services.accounts.list_accounts(include_archived=True):
            self.period_selector.hide()
            self._stack.setCurrentIndex(0)
            return
        self.period_selector.show()
        self._stack.setCurrentIndex(1)
        period = self.period_selector.period()
        dashboard = self._services.dashboard
        comparison = dashboard.comparison(period)
        self.net_worth_card.show_day(min(period.end, date.today()), period)
        self.upcoming_card.show_data(date.today())
        self.latest_card.show_period(
            period,
            LATEST_COUNT_BELOW_UPCOMING if self.upcoming_card.isVisibleTo(self) else LATEST_COUNT,
        )
        self.flow_card.show_data(comparison, dashboard.monthly_flow(period))
        self.budgets_card.show_month(self._budgets_month(), date.today())
        self.expenses_card.show_data(comparison.current, comparison.expenses_change)
        self.comparison_card.show_data(comparison)
        self._arrange()

    def _budgets_month(self) -> Month:
        """The month whose budgets the dashboard shows: the last of the period."""
        return self.period_selector.period().last_month

    def open_pay_dialog(self, charge: RecurringCharge) -> None:
        pay_charge(self, self._services, self._event_bus, charge)

    # Layout

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._arrange()
        return super().eventFilter(watched, event)

    def _arrange(self) -> None:
        """Places the cards for the available width.

        The top row is what matters at a glance: net worth, with upcoming payments and the
        latest movements beside it. Below come expenses by category next to the comparison
        with the previous period, which belong together, and last the month-by-month cash
        flow, for a closer look, with the budgets beside it when there are any. In a narrow
        window everything goes one card per row, except the top's side cards, and in a
        narrower one those too. The widest shape where every card has room for its
        minimum is chosen, so no card is ever cut; the page scrolls instead.
        """
        upcoming = self.upcoming_card.isVisibleTo(self)
        budgets = self.budgets_card.isVisibleTo(self)
        width = self._scroll.viewport().width()
        # Expenses take four of the six columns when wide, the full width otherwise.
        expenses_width = self._span_width(width, 4)
        self.expenses_card.set_legend_beside(self.expenses_card.fits_legend_beside(expenses_width))
        shape = next(
            (s for s in Shape if self._fits(self._placements(s, upcoming, budgets), width)),
            Shape.STACKED,
        )
        if shape is not Shape.WIDE:
            self.expenses_card.set_legend_beside(self.expenses_card.fits_legend_beside(width))
        layout = (shape, upcoming, budgets)
        if layout != self._layout:
            self._layout = layout
            grid = self._grid
            for card in self._cards():
                grid.removeWidget(card)
            for card, row, column, rows, columns in self._placements(*layout):
                grid.addWidget(card, row, column, rows, columns)
            used = GRID_COLUMNS if shape is Shape.WIDE else 2
            for column in range(GRID_COLUMNS):
                grid.setColumnStretch(column, 1 if column < used else 0)
        self._remeasure()

    def _placements(self, shape: Shape, upcoming: bool, budgets: bool) -> list[Placement]:
        """Where each card goes, as (card, row, column, rows spanned, columns spanned):
        six columns wide, two otherwise. Every shape is here, so a new card is placed in
        one function."""
        side = [self.upcoming_card, self.latest_card] if upcoming else [self.latest_card]
        bottom = [self.flow_card, self.budgets_card] if budgets else [self.flow_card]
        if shape is Shape.WIDE:
            return [
                (self.net_worth_card, 0, 0, 2, 4),
                *((card, row, 4, 2 // len(side), 2) for row, card in enumerate(side)),
                (self.expenses_card, 2, 0, 1, 4),
                (self.comparison_card, 2, 4, 1, 2),
                *(
                    [(self.flow_card, 3, 0, 1, 4), (self.budgets_card, 3, 4, 1, 2)]
                    if budgets
                    else [(self.flow_card, 3, 0, 1, GRID_COLUMNS)]
                ),
            ]
        together = [side] if shape is Shape.NARROW else [[card] for card in side]
        rows = [[self.net_worth_card], *together, [self.expenses_card], [self.comparison_card]]
        rows += [[card] for card in bottom]
        return [
            (card, row, column * 2 // len(cards), 1, 2 // len(cards))
            for row, cards in enumerate(rows)
            for column, card in enumerate(cards)
        ]

    def _span_width(self, width: float, columns: int) -> float:
        """How wide a card spanning ``columns`` of the six is, in a grid ``width`` wide."""
        spacing = self._grid.spacing()
        column = (width - (GRID_COLUMNS - 1) * spacing) / GRID_COLUMNS
        return columns * column + (columns - 1) * spacing

    def _fits(self, placements: list[Placement], width: float) -> bool:
        """Whether a grid ``width`` wide has room for the minimum width of every card.

        Rows share their columns, so the left edge of each column is pushed right by the
        widest card ending before it, whatever its row: the grid needs where the last
        column ends.
        """
        spacing = self._grid.spacing()
        last = max(column + columns for _card, _row, column, _rows, columns in placements)
        edges = [0] * (last + 1)  # where each column can start, at the least
        for end in range(1, last + 1):
            edges[end] = edges[end - 1]
            for card, _row, column, _rows, columns in placements:
                if column + columns == end:
                    gap = spacing if column else 0
                    # As the grid takes it: a minimum set on the card, else its hint.
                    least = max(card.minimumWidth(), card.minimumSizeHint().width())
                    needed = edges[column] + gap + least
                    edges[end] = max(edges[end], needed)
        return edges[last] <= width

    def _cards(self) -> list[QWidget]:
        return [
            self.net_worth_card,
            self.upcoming_card,
            self.latest_card,
            self.flow_card,
            self.budgets_card,
            self.expenses_card,
            self.comparison_card,
        ]

    def _remeasure(self) -> None:
        """Makes the page scroll instead of squeezing the cards.

        The scroll area only takes its content's minimum height when it is resized, so a
        card that appears or a theme with other fonts would leave the cards squeezed. The
        content's minimum height is set explicitly instead, once Qt has applied pending
        style and layout changes.
        """
        # With the page as context, the call is dropped if the page is gone by then.
        QTimer.singleShot(0, self, self._apply_minimum_height)

    def _apply_minimum_height(self) -> None:
        self._grid.activate()
        self._scroll.widget().setMinimumHeight(self._grid.minimumSize().height())
        QCoreApplication.postEvent(self._scroll, QEvent(QEvent.Type.LayoutRequest))

    def _bring_data(self) -> None:
        """Restores the copy saved on another computer, starting in the pen drive of the
        last copy outside the computer when it is plugged in."""
        start = self._services.backups.external_folder() or Path.home()
        restore_copy(
            self.window(),
            self._services,
            self._event_bus,
            self._theme_manager,
            start,
            self.bring_data_button,
        )

    def _welcome_card(self) -> Card:
        card = Card()
        title = QLabel(_("Te damos la bienvenida a Nodus"))
        title.setObjectName("DialogTitle")
        text = muted_label(
            _("Crea una cuenta por cada lugar donde tengas dinero y registra tus movimientos.")
        )
        text.setWordWrap(True)
        self.create_account_button = QPushButton(_("Agregar mi primera cuenta"))
        self.create_account_button.setObjectName("PrimaryButton")
        self.create_account_button.clicked.connect(
            lambda: self.navigate_requested.emit(PageId.ACCOUNTS)
        )
        # Nodus on a new computer: the copy saved on the old one brings everything along.
        self.bring_data_button = secondary_button(
            _("Traer mis datos de otra computadora"), self._bring_data
        )
        buttons = QHBoxLayout()
        buttons.addWidget(self.create_account_button)
        buttons.addWidget(self.bring_data_button)
        buttons.addStretch()
        card.body.addWidget(title)
        card.body.addWidget(text)
        card.body.addSpacing(Space.S)
        card.body.addLayout(buttons)
        return card
