"""Analysis section: long trends of spending, income, savings and net worth."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QScrollArea, QStackedWidget

from nodus.models.period import Period
from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.analysis.cash_flow_view import CashFlowView
from nodus.ui.pages.analysis.common import AnalysisView
from nodus.ui.pages.analysis.net_worth_view import NetWorthView
from nodus.ui.pages.analysis.trends_view import TrendsView
from nodus.ui.pages.base.page import Page
from nodus.ui.period_selector import PeriodSelector
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.style import scrolling

DEFAULT_MONTHS = 12


class AnalysisPage(Page):
    """One report at a time, chosen with the tabs, over a period shared by all of them
    (the last 12 months at first). Only the report on screen is computed."""

    transactions_requested = Signal(object)  # TransactionFocus
    navigate_requested = Signal(object)  # PageId

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.ANALYSIS.label)
        net_worth = NetWorthView(services, theme_manager)
        net_worth.card.currency_changed.connect(event_bus.net_worth_currency_changed)
        net_worth.rate_requested.connect(lambda: self.navigate_requested.emit(PageId.SETTINGS))
        self.views: list[AnalysisView] = [
            TrendsView(services, theme_manager),
            CashFlowView(services, theme_manager),
            net_worth,
        ]
        self.tabs = self.set_tabs(
            ["Tendencias", "Flujo de caja", "Patrimonio neto"],
            [view.DESCRIPTION for view in self.views],
        )
        self.period_selector = PeriodSelector(Period.last_months(DEFAULT_MONTHS, date.today()))
        self.add_header_widget(self.period_selector)

        self._stack = QStackedWidget()
        for view in self.views:
            view.transactions_requested.connect(self.transactions_requested)
            scroll = scrolling(view, horizontal=False)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            self._stack.addWidget(scroll)
        self.content_layout.addWidget(self._stack, stretch=1)

        self.tabs.changed.connect(self._show_tab)
        self.period_selector.period_changed.connect(lambda _period: self.refresh())
        for signal in (
            event_bus.transactions_changed,
            event_bus.categories_changed,
            event_bus.payees_changed,
            event_bus.exchange_rates_changed,
            event_bus.accounts_changed,
        ):
            signal.connect(self.request_refresh)

    @property
    def current_view(self) -> AnalysisView:
        return self.views[self.tabs.index()]

    def refresh(self) -> None:
        self.current_view.show_period(self.period_selector.period())

    def _show_tab(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self.refresh()
