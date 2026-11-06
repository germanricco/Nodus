import json
from datetime import date
from decimal import Decimal

import pytest

from nodus.services.rate_feed_service import DOLARAPI_URL, MANUAL, RateFeedService

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

    return RateFeedService(services.exchange_rates, services.settings, fetch)


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
