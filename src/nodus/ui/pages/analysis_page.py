"""Analysis section: long trends of spending, income, savings and net worth."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QStackedWidget

from nodus.models.period import Period
from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.analysis_views import AnalysisView, CashFlowView, NetWorthView, TrendsView
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.segmented import SegmentedControl

DEFAULT_MONTHS = 12


class AnalysisPage(Page):
    """One report at a time, chosen with the tabs, over a period shared by all of them
    (the last 12 months at first). Only the report on screen is computed."""

    transactions_requested = Signal(object, object, object)  # Period, category id, payee id
    navigate_requested = Signal(object)  # PageId

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Análisis")
        net_worth = NetWorthView(services, theme_manager)
        net_worth.rate_requested.connect(lambda: self.navigate_requested.emit(PageId.SETTINGS))
        self.views: list[AnalysisView] = [
            TrendsView(services, theme_manager),
            CashFlowView(services, theme_manager),
            net_worth,
        ]
        self.tabs = SegmentedControl(["Tendencias", "Flujo de caja", "Patrimonio"])
        self.period_selector = PeriodSelector(Period.last_months(DEFAULT_MONTHS, date.today()))
        self.add_header_widget(self.tabs)
        self.add_header_widget(self.period_selector)

        self._stack = QStackedWidget()
        for view in self.views:
            view.transactions_requested.connect(self.transactions_requested)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setWidget(view)
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
            signal.connect(self._data_changed)

    @property
    def current_view(self) -> AnalysisView:
        return self.views[self.tabs.index()]

    def refresh(self) -> None:
        self.current_view.show_period(self.period_selector.period())

    def _show_tab(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self.refresh()

    def _data_changed(self) -> None:
        # Hidden pages are refreshed by the main window when shown.
        if self.isVisible():
            self.refresh()
