"""Dashboard: how much there is, how the period went and where the money went."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from nodus.models.period import Month, Period
from nodus.models.recurring_charge import RecurringCharge
from nodus.services.container import Services
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.dashboard_cards import (
    LATEST_COUNT,
    LATEST_COUNT_BELOW_UPCOMING,
    BudgetsCard,
    CashFlowCard,
    ComparisonCard,
    ExpensesCard,
    LatestTransactionsCard,
    UpcomingPaymentsCard,
    muted_label,
)
from nodus.ui.pages.page import Page
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.net_worth_card import NetWorthCard
from nodus.ui.widgets.period_selector import PeriodSelector

# Below this page width, the cards go one per row.
NARROW_WIDTH = 900


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
        super().__init__("Dashboard")
        self._services = services
        self._event_bus = event_bus
        self.period_selector = PeriodSelector()
        self.add_header_widget(self.period_selector)

        self.net_worth_card = NetWorthCard(services, theme_manager)
        self.net_worth_card.set_amounts_hidden(services.settings.amounts_hidden())
        event_bus.amounts_hidden_changed.connect(self.net_worth_card.set_amounts_hidden)
        self.net_worth_card.rate_requested.connect(
            lambda: self.navigate_requested.emit(PageId.SETTINGS)
        )
        self.latest_card = LatestTransactionsCard(services, theme_manager)
        self.latest_card.see_all_requested.connect(
            lambda: self.transactions_requested.emit(
                TransactionFocus(self.period_selector.period())
            )
        )
        self.upcoming_card = UpcomingPaymentsCard(services)
        self.upcoming_card.pay_requested.connect(self.open_pay_dialog)
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
        self._layout: tuple[bool, bool, bool] | None = None
        # Owned by the grid page from the start, so a card left out of the grid (upcoming
        # payments without charges) never becomes a window of its own when shown.
        for card in self._cards():
            card.setParent(grid_page)
        scroll = self._scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(grid_page)

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
        theme_manager.theme_changed.connect(self._data_changed)
        theme_manager.theme_changed.connect(self._remeasure)
        for signal in (
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
            event_bus.recurring_changed,
            event_bus.budgets_changed,
        ):
            signal.connect(self._data_changed)

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
        PayChargeDialog(self._services, self._event_bus, charge, parent=self.window()).exec()

    # Layout

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._arrange()

    def _arrange(self) -> None:
        """Places the cards for the available width.

        The top row is what matters at a glance: net worth, with upcoming payments and the
        latest movements beside it. Below come expenses by category next to the comparison
        with the previous period, which belong together, and last the month-by-month cash
        flow, for a closer look, with the budgets beside it when there are any. In a narrow
        window everything goes one card per row, except the top's side cards.
        The page scrolls instead of squeezing the cards.
        """
        narrow = self.width() < NARROW_WIDTH
        upcoming = self.upcoming_card.isVisibleTo(self)
        budgets = self.budgets_card.isVisibleTo(self)
        # Expenses take the full width when narrow, four of the six columns otherwise.
        width = self._scroll.viewport().width()
        column = (width - 5 * self._grid.spacing()) / 6
        expenses_width = width if narrow else 4 * column + 3 * self._grid.spacing()
        beside = self.expenses_card.fits_legend_beside(expenses_width)
        self.expenses_card.set_legend_beside(beside)
        layout = (narrow, upcoming, budgets)
        if layout != self._layout:
            self._layout = layout
            grid = self._grid
            for card in self._cards():
                grid.removeWidget(card)
            if narrow:
                rows = [
                    [(self.net_worth_card, 2)],
                    [(self.upcoming_card, 1), (self.latest_card, 1)]
                    if upcoming
                    else [(self.latest_card, 2)],
                    [(self.expenses_card, 2)],
                    [(self.comparison_card, 2)],
                    [(self.flow_card, 2)],
                ]
                if budgets:
                    rows.append([(self.budgets_card, 2)])
                self._place(rows)
            else:
                grid.addWidget(self.net_worth_card, 0, 0, 2, 4)
                if upcoming:
                    grid.addWidget(self.upcoming_card, 0, 4, 1, 2)
                    grid.addWidget(self.latest_card, 1, 4, 1, 2)
                else:
                    grid.addWidget(self.latest_card, 0, 4, 2, 2)
                grid.addWidget(self.expenses_card, 2, 0, 1, 4)
                grid.addWidget(self.comparison_card, 2, 4, 1, 2)
                if budgets:
                    grid.addWidget(self.flow_card, 3, 0, 1, 4)
                    grid.addWidget(self.budgets_card, 3, 4, 1, 2)
                else:
                    grid.addWidget(self.flow_card, 3, 0, 1, 6)
            for column in range(6):
                grid.setColumnStretch(column, 1 if column < (2 if narrow else 6) else 0)
        self._remeasure()

    def _place(self, rows: list[list[tuple[QWidget, int]]]) -> None:
        """Adds each row of (card, columns spanned) below the previous one."""
        for row_index, row in enumerate(rows):
            column = 0
            for card, span in row:
                self._grid.addWidget(card, row_index, column, 1, span)
                column += span

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

    def _data_changed(self) -> None:
        # Hidden pages are refreshed by the main window when shown.
        if self.isVisible():
            self.refresh()

    def _welcome_card(self) -> Card:
        card = Card()
        title = QLabel("Te damos la bienvenida a Nodus")
        title.setObjectName("DialogTitle")
        text = muted_label(
            "Crea una cuenta por cada lugar donde tengas dinero y registra tus movimientos."
        )
        text.setWordWrap(True)
        self.create_account_button = QPushButton("Agregar mi primera cuenta")
        self.create_account_button.setObjectName("PrimaryButton")
        self.create_account_button.clicked.connect(
            lambda: self.navigate_requested.emit(PageId.ACCOUNTS)
        )
        buttons = QHBoxLayout()
        buttons.addWidget(self.create_account_button)
        buttons.addStretch()
        card.body.addWidget(title)
        card.body.addWidget(text)
        card.body.addSpacing(Space.S)
        card.body.addLayout(buttons)
        return card
