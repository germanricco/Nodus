"""Ajustes: theme, exchange rates, the data file and Nodus itself, one card each."""

from __future__ import annotations

from PySide6.QtCore import Signal

from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.base.page import Page
from nodus.ui.pages.settings.about_card import AboutCard
from nodus.ui.pages.settings.data_card import DataCard
from nodus.ui.pages.settings.general_card import GeneralCard
from nodus.ui.pages.settings.rates_card import RatesCard
from nodus.ui.theme.theme_manager import ThemeManager


class SettingsPage(Page):
    """Preferences grouped in cards; each card reads and saves its own."""

    tour_requested = Signal()
    help_requested = Signal()

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.SETTINGS.label)
        self.general = GeneralCard(services, theme_manager)
        self.rates = RatesCard(services, event_bus)
        self.data = DataCard(services, event_bus, theme_manager)
        self.about = AboutCard(services)
        self._cards = (self.general, self.rates, self.data, self.about)

        sections = self.scrolling_body()
        for card in self._cards:
            sections.addWidget(card)
        sections.addStretch()

        self.about.tour_requested.connect(self.tour_requested)
        self.about.help_requested.connect(self.help_requested)
        self.data.restored.connect(self.refresh)

    def refresh(self) -> None:
        for card in self._cards:
            card.refresh()
