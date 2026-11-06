"""Dashboard: how much there is, how the period went and where the money went."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.dashboard_cards import (
    CashFlowCard,
    ComparisonCard,
    ExpensesCard,
    LatestTransactionsCard,
    muted_label,
)
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.net_worth_card import NetWorthCard
from nodus.ui.widgets.period_selector import PeriodSelector


class DashboardPage(Page):
    """Net worth with its trend, the period's cash flow, expenses by category and against
    the previous period, and the latest movements. Without accounts it shows how to get
    started instead.

    The cards are built once. When data changes while the dashboard is on screen (a
    transaction saved from the top bar, for instance), they receive the new figures and
    their charts move to them; when it is hidden, it refreshes on being shown again.
    """

    navigate_requested = Signal(object)  # PageId
    transactions_requested = Signal(object, object)  # Period, category id or None

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Dashboard")
        self._services = services
        self.period_selector = PeriodSelector()
        self.add_header_widget(self.period_selector)

        self.net_worth_card = NetWorthCard(services, theme_manager)
        self.net_worth_card.rate_requested.connect(
            lambda: self.navigate_requested.emit(PageId.SETTINGS)
        )
        self.latest_card = LatestTransactionsCard(services, theme_manager)
        self.latest_card.see_all_requested.connect(
            lambda: self.transactions_requested.emit(self.period_selector.period(), None)
        )
        self.flow_card = CashFlowCard(theme_manager)
        self.expenses_card = ExpensesCard(theme_manager)
        self.comparison_card = ComparisonCard()
        for card in (self.expenses_card, self.comparison_card):
            card.category_clicked.connect(
                lambda category_id: self.transactions_requested.emit(
                    self.period_selector.period(), category_id
                )
            )

        grid_page = QWidget()
        grid = QGridLayout(grid_page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)
        grid.addWidget(self.net_worth_card, 0, 0, 1, 2)
        grid.addWidget(self.latest_card, 0, 2)
        grid.addWidget(self.flow_card, 1, 0)
        grid.addWidget(self.expenses_card, 1, 1)
        grid.addWidget(self.comparison_card, 1, 2)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
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
        for signal in (
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
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
        self.latest_card.show_period(period)
        self.flow_card.show_data(comparison, dashboard.monthly_flow(period))
        self.expenses_card.show_data(comparison.current, comparison.expenses_change)
        self.comparison_card.show_data(comparison)

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
        self.create_account_button = QPushButton("Crear mi primera cuenta")
        self.create_account_button.setObjectName("PrimaryButton")
        self.create_account_button.clicked.connect(
            lambda: self.navigate_requested.emit(PageId.ACCOUNTS)
        )
        buttons = QHBoxLayout()
        buttons.addWidget(self.create_account_button)
        buttons.addStretch()
        card.body.addWidget(title)
        card.body.addWidget(text)
        card.body.addSpacing(8)
        card.body.addLayout(buttons)
        return card
