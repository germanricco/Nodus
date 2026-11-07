import json
from datetime import date
from decimal import Decimal

import pytest
from factories import clp, eur

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.rate_feed_service import DOLARAPI_URL, MANUAL, QUOTES_URL, RateFeedService

TODAY = date(2026, 11, 6)
QUOTES = [
    {"casa": "oficial", "compra": 1520, "venta": 1570},
    {"casa": "blue", "compra": 1535, "venta": 1555},
    {"casa": "bolsa", "compra": 1573.8, "venta": 1588.5},
]


def feed_with(services, body: bytes | Exception, requests: list | None = None) -> RateFeedService:
    def fetch(url):
        if requests is not None:
            requests.append(url)
        if isinstance(body, Exception):
            raise body
        return body

    return RateFeedService(services.exchange_rates, services.settings, services.accounts, fetch)


def test_new_database_starts_on_mep_and_keeps_it(services):
    feed = feed_with(services, b"[]")

    assert feed.source() == "bolsa"
    services.exchange_rates.set_rate(TODAY, Decimal("1500"))
    assert feed.source() == "bolsa"


def test_database_with_rates_starts_on_manual(services):
    services.exchange_rates.set_rate(TODAY, Decimal("1500"))

    assert feed_with(services, b"[]").source() == MANUAL


def test_unknown_source_is_rejected(services):
    with pytest.raises(ValueError):
        feed_with(services, b"[]").set_source("euro")


@pytest.mark.parametrize(("source", "expected"), [("bolsa", "1588.5"), ("blue", "1555")])
def test_fetch_takes_the_selling_price_of_the_source(services, source, expected):
    requests = []
    feed = feed_with(services, json.dumps(QUOTES).encode(), requests)

    assert feed.fetch(source) == Decimal(expected)
    assert requests == [DOLARAPI_URL]


@pytest.mark.parametrize(
    "body",
    [
        OSError("sin conexión"),
        b"no json",
        b"{}",
        json.dumps([{"casa": "blue"}]).encode(),
        json.dumps([{"casa": "blue", "venta": 0}]).encode(),
        json.dumps([{"casa": "blue", "venta": "abc"}]).encode(),
    ],
)
def test_fetch_failures_give_none(services, body):
    assert feed_with(services, body).fetch("blue") is None


def test_due_only_with_automatic_source_and_no_rate_today(services):
    feed = feed_with(services, b"[]")
    feed.set_source("blue")
    assert feed.is_due(TODAY)

    services.exchange_rates.set_rate(date(2026, 11, 5), Decimal("1500"))
    assert feed.is_due(TODAY)

    services.exchange_rates.set_rate(TODAY, Decimal("1500"))
    assert not feed.is_due(TODAY)

    feed.set_source(MANUAL)
    services.exchange_rates.delete(services.exchange_rates.rate_on(TODAY).id)
    assert not feed.is_due(TODAY)


def test_save_records_todays_rate(services):
    feed_with(services, b"[]").save(Decimal("1588.5"), TODAY)

    assert services.exchange_rates.rate_on(TODAY).rate == Decimal("1588.5")


OFFICIAL = [
    {"moneda": "USD", "casa": "oficial", "venta": 1570},
    {"moneda": "EUR", "casa": "oficial", "venta": 1738.25},
    {"moneda": "CLP", "casa": "oficial", "venta": 1.5784},
]


def feed_by_url(services, bodies: dict[str, bytes], requests: list) -> RateFeedService:
    """A feed whose fake DolarApi answers each address with its own body."""

    def fetch(url):
        requests.append(url)
        return bodies[url]

    return RateFeedService(services.exchange_rates, services.settings, services.accounts, fetch)


class TestOtherCurrencies:
    def test_the_dollar_always_and_the_others_only_when_an_account_holds_them(self, services):
        feed = feed_with(services, b"[]")
        assert feed.currencies() == [Currency.USD]

        services.accounts.create("Viaje", AccountType.CASH, Currency.CLP, clp("0"))
        archived = services.accounts.create("Europa", AccountType.CASH, Currency.EUR, eur("0"))
        services.accounts.set_archived(archived.id, True)

        assert feed.currencies() == [Currency.USD, Currency.CLP]

    def test_due_is_per_currency(self, services):
        services.accounts.create("Europa", AccountType.CASH, Currency.EUR, eur("0"))
        feed = feed_with(services, b"[]")
        feed.set_source("blue")
        services.exchange_rates.set_rate(TODAY, Decimal("1500"))

        assert feed.due(TODAY) == [Currency.EUR]

    def test_fetch_all_takes_the_chosen_dollar_and_the_official_rest(self, services):
        requests = []
        bodies = {
            DOLARAPI_URL: json.dumps(QUOTES).encode(),
            QUOTES_URL: json.dumps(OFFICIAL).encode(),
        }
        feed = feed_by_url(services, bodies, requests)

        rates = feed.fetch_all("blue", [Currency.USD, Currency.EUR, Currency.CLP])

        assert rates == {
            Currency.USD: Decimal("1555"),
            Currency.EUR: Decimal("1738.25"),
            Currency.CLP: Decimal("1.5784"),
        }
        assert sorted(requests) == sorted([DOLARAPI_URL, QUOTES_URL])

    def test_only_the_dollar_needs_a_single_request(self, services):
        requests = []
        feed = feed_by_url(services, {DOLARAPI_URL: json.dumps(QUOTES).encode()}, requests)

        assert feed.fetch_all("bolsa", [Currency.USD]) == {Currency.USD: Decimal("1588.5")}
        assert requests == [DOLARAPI_URL]

    def test_a_currency_missing_from_the_answer_is_left_out(self, services):
        body = json.dumps([OFFICIAL[1], {"moneda": "CLP", "venta": 0}]).encode()

        rates = feed_with(services, body).fetch_official([Currency.EUR, Currency.CLP])

        assert rates == {Currency.EUR: Decimal("1738.25")}

    def test_no_internet_gives_nothing(self, services):
        assert feed_with(services, OSError("sin conexión")).fetch_official([Currency.EUR]) == {}

    def test_save_records_the_rate_of_its_currency(self, services):
        feed_with(services, b"[]").save(Decimal("1738.25"), TODAY, Currency.EUR)

        assert services.exchange_rates.rate_on(TODAY, Currency.EUR).rate == Decimal("1738.25")
        assert services.exchange_rates.rate_on(TODAY) is None
