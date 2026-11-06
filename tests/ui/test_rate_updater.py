import dataclasses
import json
from datetime import date
from decimal import Decimal

import pytest

from nodus.services.rate_feed_service import SOURCES, RateFeedService
from nodus.ui.main_window import MainWindow
from nodus.ui.navigation import PageId

QUOTES = json.dumps([{"casa": "blue", "venta": 1555}, {"casa": "bolsa", "venta": 1588.5}]).encode()


@pytest.fixture
def answer():
    """What the fake DolarApi returns; a test may replace it with an exception."""
    return {"body": QUOTES}


@pytest.fixture
def offline_services(services, answer):
    def fetch(_url):
        if isinstance(answer["body"], Exception):
            raise answer["body"]
        return answer["body"]

    feed = RateFeedService(services.exchange_rates, services.settings, fetch)
    return dataclasses.replace(services, rate_feed=feed)


@pytest.fixture
def offline_window(qtbot, offline_services, event_bus, theme_manager) -> MainWindow:
    window = MainWindow(offline_services, event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()
    return window


def todays_rate(services) -> Decimal | None:
    rate = services.exchange_rates.rate_on(date.today())
    return rate.rate if rate and rate.rate_date == date.today() else None


def test_startup_saves_todays_rate(qtbot, offline_services, event_bus, offline_window):
    offline_services.rate_feed.set_source("blue")

    with qtbot.waitSignal(event_bus.exchange_rates_changed):
        offline_window.update_exchange_rate()

    assert todays_rate(offline_services) == Decimal("1555")


def test_startup_keeps_a_rate_typed_today(qtbot, offline_services, offline_window):
    offline_services.rate_feed.set_source("blue")
    offline_services.exchange_rates.set_rate(date.today(), Decimal("1500"))

    offline_window.update_exchange_rate()
    qtbot.wait(100)

    assert todays_rate(offline_services) == Decimal("1500")


def test_choosing_a_source_in_settings_fetches_it(qtbot, offline_services, offline_window):
    offline_services.exchange_rates.set_rate(date.today(), Decimal("1500"))
    offline_services.rate_feed.set_source("manual")
    offline_window.show_page(PageId.SETTINGS)
    page = offline_window.page(PageId.SETTINGS)
    assert not page.refresh_rate_button.isVisible()

    page.rate_source_input.set_index(list(SOURCES).index("bolsa"))

    qtbot.waitUntil(lambda: todays_rate(offline_services) == Decimal("1588.5"))
    assert offline_services.rate_feed.source() == "bolsa"
    assert page.refresh_rate_button.isVisible()


def test_failed_fetch_is_reported_in_settings(qtbot, offline_services, answer, offline_window):
    answer["body"] = OSError("sin conexión")
    offline_services.rate_feed.set_source("blue")
    offline_window.show_page(PageId.SETTINGS)
    page = offline_window.page(PageId.SETTINGS)

    page.refresh_rate_button.click()

    qtbot.waitUntil(lambda: page.rate_source_row.detail.text() == "Sin conexión")
    assert todays_rate(offline_services) is None
