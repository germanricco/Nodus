"""Fetches the day's exchange rates in the background and saves them."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from nodus.models.currency import Currency
from nodus.services.container import Services
from nodus.ui.background import BackgroundCall
from nodus.ui.event_bus import EventBus


class RateUpdater(QObject):
    """Runs the DolarApi requests off the interface thread and saves the results on it.

    The database connection belongs to the interface thread, so only the download happens
    in the background. ``updated`` carries the rates that came; ``failed`` means none did.
    """

    updated = Signal(object)  # dict[Currency, Decimal]
    failed = Signal()

    def __init__(self, services: Services, event_bus: EventBus, parent: QObject | None = None):
        super().__init__(parent)
        self._feed = services.rate_feed
        self._event_bus = event_bus
        self._call: BackgroundCall | None = None

    def update(self, force: bool = False) -> None:
        """Fetches today's rates if the source is automatic. Without ``force``, only the
        ones today has no rate for yet, so a rate typed by hand is never replaced on
        startup."""
        if not self._feed.is_automatic():
            return
        today = date.today()
        currencies = self._feed.currencies() if force else self._feed.due(today)
        if not currencies:
            return
        source = self._feed.source()
        self._call = BackgroundCall(lambda: self._feed.fetch_all(source, currencies), parent=self)
        self._call.done.connect(lambda rates: self._save(rates, today, force))
        self._call.start()

    def _save(self, rates: dict[Currency, Decimal], today: date, force: bool) -> None:
        if not rates:
            self.failed.emit()
            return
        # Checked again: the user may have typed a rate while the request was running.
        saved = False
        for currency, value in rates.items():
            if force or self._feed.is_due(today, currency):
                self._feed.save(value, today, currency)
                saved = True
        if saved:
            self._event_bus.exchange_rates_changed.emit()
        self.updated.emit(rates)
