"""Brings the day's dollar rate from DolarApi, so the user does not have to type it."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.http import Fetch
from nodus.services.settings_service import SettingsService

DOLARAPI_URL = "https://dolarapi.com/v1/dolares"
MANUAL = "manual"
# Where the rate comes from, in the order the settings show them. Keys are DolarApi's
# "casa" codes; MEP is listed there as "bolsa".
SOURCES = {MANUAL: "Manual", "bolsa": "MEP", "blue": "Blue", "oficial": "Oficial"}
DEFAULT_SOURCE = "bolsa"


class RateFeedService:
    """Fetches the selling price of the chosen dollar and saves it as today's rate.

    A rate the user typed for today always wins over the automatic one, unless they ask to
    update explicitly. Fetching only touches the network, so it can run on a worker thread;
    saving goes through ``ExchangeRateService`` on the interface thread.
    """

    def __init__(
        self, exchange_rates: ExchangeRateService, settings: SettingsService, fetch: Fetch
    ) -> None:
        self._exchange_rates = exchange_rates
        self._settings = settings
        self._fetch = fetch

    def source(self) -> str:
        """The chosen source.

        The first time, a database that already has rates stays on Manual (nothing changes
        behind the user's back) and a new one starts on MEP. That choice is saved at once,
        so typing a rate later does not silently switch a new database to Manual.
        """
        saved = self._settings.rate_source()
        if saved in SOURCES:
            return saved
        default = MANUAL if self._exchange_rates.history() else DEFAULT_SOURCE
        self._settings.set_rate_source(default)
        return default

    def set_source(self, source: str) -> None:
        if source not in SOURCES:
            raise ValueError(f"Unknown rate source: {source}")
        self._settings.set_rate_source(source)

    def is_automatic(self) -> bool:
        return self.source() != MANUAL

    def is_due(self, today: date) -> bool:
        """Whether opening the app should fetch: automatic source and no rate for today."""
        current = self._exchange_rates.rate_on(today)
        return self.is_automatic() and (current is None or current.rate_date != today)

    def fetch(self, source: str) -> Decimal | None:
        """Today's selling price of ``source`` in pesos, or None if it cannot be had.

        No internet or an unexpected answer gives None: the last saved rate keeps working.
        """
        try:
            quotes = json.loads(self._fetch(DOLARAPI_URL))
            quote = next(q for q in quotes if q["casa"] == source)
            value = Decimal(str(quote["venta"]))
        except (OSError, ValueError, KeyError, TypeError, StopIteration, InvalidOperation):
            return None
        return value if value > 0 else None

    def save(self, value: Decimal, today: date) -> None:
        self._exchange_rates.set_rate(today, value)
