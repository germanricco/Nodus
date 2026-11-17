"""Fetches the day's exchange rates in the background and saves them."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from weakref import WeakKeyDictionary

from PySide6.QtCore import QObject, Signal

from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.services.container import Services
from nodus.ui.background import BackgroundCall
from nodus.ui.event_bus import EventBus
from nodus.ui.text.labels import rate_text


class RateUpdater(QObject):
    """Runs the DolarApi requests off the interface thread and saves the results on it.

    The database connection belongs to the interface thread, so only the download happens
    in the background. ``updated`` carries the rates that came and were saved; ``failed``
    means none came.
    """

    updated = Signal(object)  # dict[Currency, Decimal]
    failed = Signal()

    def __init__(self, services: Services, event_bus: EventBus, parent: QObject | None = None):
        super().__init__(parent)
        self._feed = services.rate_feed
        self._event_bus = event_bus
        self._call: BackgroundCall | None = None
        self.running = False

    def update(self, force: bool = False) -> None:
        """Fetches today's rates if the source is automatic. Without ``force``, only the
        ones today has no rate for yet, so a rate typed by hand is never replaced on
        startup. While a request runs, another is not started."""
        if self.running or not self._feed.is_automatic():
            return
        today = date.today()
        currencies = self._feed.currencies() if force else self._feed.due(today)
        if not currencies:
            return
        source = self._feed.source()
        self._call = BackgroundCall(lambda: self._feed.fetch_all(source, currencies), parent=self)
        self._call.done.connect(lambda rates: self._save(rates, today, force))
        self._call.failed.connect(lambda: self._save({}, today, force))
        self.running = True
        self._call.start()

    def _save(self, rates: dict[Currency, Decimal], today: date, force: bool) -> None:
        self.running = False
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


_SHARED: WeakKeyDictionary[EventBus, RateUpdater] = WeakKeyDictionary()


def shared_rate_updater(services: Services, event_bus: EventBus) -> RateUpdater:
    """The one ``RateUpdater`` of the app, which Ajustes and the start of Nodus share: two
    of them could ask DolarApi at once and save the same day twice. It lives as long as
    ``event_bus``, which is one per app."""
    updater = _SHARED.get(event_bus)
    if updater is None:
        updater = RateUpdater(services, event_bus, parent=event_bus)
        _SHARED[event_bus] = updater
    return updater


def updated_text(rates: dict[Currency, Decimal]) -> str:
    """The toast once rates arrive: the dollar's, which is the one people look at."""
    if Currency.USD in rates:
        dollar = rate_text(Currency.USD, HOME_CURRENCY, rates[Currency.USD])
        return f"Cotización actualizada: {dollar}"
    return "Cotizaciones actualizadas."
