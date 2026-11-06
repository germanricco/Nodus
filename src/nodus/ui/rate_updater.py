"""Fetches the day's dollar rate in the background and saves it."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from nodus.services.container import Services
from nodus.ui.background import BackgroundCall
from nodus.ui.event_bus import EventBus


class RateUpdater(QObject):
    """Runs the DolarApi request off the interface thread and saves the result on it.

    The database connection belongs to the interface thread, so only the download happens
    in the background. ``updated`` carries the saved rate; ``failed`` means no rate came.
    """

    updated = Signal(object)  # Decimal
    failed = Signal()

    def __init__(self, services: Services, event_bus: EventBus, parent: QObject | None = None):
        super().__init__(parent)
        self._feed = services.rate_feed
        self._event_bus = event_bus
        self._call: BackgroundCall | None = None

    def update(self, force: bool = False) -> None:
        """Fetches today's rate if the source is automatic. Without ``force``, only when
        today has no rate yet, so a rate typed by hand is never replaced on startup."""
        today = date.today()
        if not self._feed.is_automatic() or not (force or self._feed.is_due(today)):
            return
        source = self._feed.source()
        self._call = BackgroundCall(lambda: self._feed.fetch(source), parent=self)
        self._call.done.connect(lambda value: self._save(value, today, force))
        self._call.start()

    def _save(self, value: Decimal | None, today: date, force: bool) -> None:
        if value is None:
            self.failed.emit()
            return
        # Checked again: the user may have typed a rate while the request was running.
        if force or self._feed.is_due(today):
            self._feed.save(value, today)
            self._event_bus.exchange_rates_changed.emit()
        self.updated.emit(value)
