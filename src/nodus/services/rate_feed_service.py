"""Brings the day's rates from DolarApi, so the user does not have to type them."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from nodus.models.currency import Currency
from nodus.services.account_service import AccountService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.http import Fetch
from nodus.services.settings_service import SettingsService

DOLARAPI_URL = "https://dolarapi.com/v1/dolares"
# Official rates of the other currencies DolarApi publishes, keyed by "moneda".
QUOTES_URL = "https://dolarapi.com/v1/cotizaciones"
MANUAL = "manual"
# Where the dollar rate comes from, in the order the settings show them. Keys are
# DolarApi's "casa" codes; MEP is listed there as "bolsa".
SOURCES = {MANUAL: "Manual", "bolsa": "MEP", "blue": "Blue", "oficial": "Oficial"}
DEFAULT_SOURCE = "bolsa"
_BAD_ANSWER = (
    OSError,
    ValueError,
    KeyError,
    TypeError,
    AttributeError,
    StopIteration,
    InvalidOperation,
)


class RateFeedService:
    """Fetches the selling price of each foreign currency in use and saves it as today's
    rate.

    The dollar follows the source the user chose (MEP, blue…); the euro and the Chilean
    peso have a single market, so they take the official rate whenever the source is
    automatic. A rate the user typed for today always wins over the automatic one, unless
    they ask to update explicitly. Fetching only touches the network, so it can run on a
    worker thread; saving goes through ``ExchangeRateService`` on the interface thread.
    """

    def __init__(
        self,
        exchange_rates: ExchangeRateService,
        settings: SettingsService,
        accounts: AccountService,
        fetch: Fetch,
    ) -> None:
        self._exchange_rates = exchange_rates
        self._settings = settings
        self._accounts = accounts
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

    def currencies(self) -> list[Currency]:
        """The currencies whose rate is kept: the dollar, which the totals always use, and
        any other foreign currency an active account holds."""
        held = {account.currency for account in self._accounts.list_accounts()}
        return [c for c in Currency if c is Currency.USD or (c.is_foreign and c in held)]

    def is_due(self, today: date, currency: Currency = Currency.USD) -> bool:
        """Whether opening the app should fetch ``currency``: automatic source and no rate
        for today."""
        current = self._exchange_rates.rate_on(today, currency)
        return self.is_automatic() and (current is None or current.rate_date != today)

    def due(self, today: date) -> list[Currency]:
        """The currencies in use that have no rate for today yet."""
        return [c for c in self.currencies() if self.is_due(today, c)]

    def fetch(self, source: str) -> Decimal | None:
        """Today's selling price of the dollar from ``source`` in pesos, or None if it
        cannot be had.

        No internet or an unexpected answer gives None: the last saved rate keeps working.
        """
        try:
            quotes = json.loads(self._fetch(DOLARAPI_URL))
            quote = next(q for q in quotes if q["casa"] == source)
            return _positive(quote["venta"])
        except _BAD_ANSWER:
            return None

    def fetch_official(self, currencies: list[Currency]) -> dict[Currency, Decimal]:
        """Today's official selling price of each of ``currencies`` that DolarApi
        publishes; the ones it lacks, or all of them without internet, are left out."""
        if not currencies:
            return {}
        try:
            quotes = json.loads(self._fetch(QUOTES_URL))
            by_code = {q.get("moneda"): q for q in quotes}
        except _BAD_ANSWER:
            return {}
        rates = {}
        for currency in currencies:
            try:
                value = _positive(by_code[currency.value]["venta"])
            except _BAD_ANSWER:
                continue
            if value is not None:
                rates[currency] = value
        return rates

    def fetch_all(self, source: str, currencies: list[Currency]) -> dict[Currency, Decimal]:
        """Today's rate of each of ``currencies``: the dollar from ``source``, the others
        official. Whatever could not be had is missing from the result."""
        rates = self.fetch_official([c for c in currencies if c is not Currency.USD])
        if Currency.USD in currencies and (dollar := self.fetch(source)) is not None:
            rates[Currency.USD] = dollar
        return rates

    def save(self, value: Decimal, today: date, currency: Currency = Currency.USD) -> None:
        self._exchange_rates.set_rate(today, value, currency)


def _positive(value: object) -> Decimal | None:
    """``value`` as a Decimal if it is a price above zero."""
    number = Decimal(str(value))
    return number if number > 0 else None
