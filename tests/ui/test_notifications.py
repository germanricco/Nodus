import dataclasses
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from factories import ars, charge_draft

from nodus.services.notification_service import NoticeKind
from nodus.services.update_service import UpdateService
from nodus.ui import main_window as main_window_module
from nodus.ui.main_window import MainWindow
from nodus.ui.navigation import PageId

NEWER = json.dumps({"tag_name": "v9.0.0", "html_url": "https://example.com/v9"}).encode()


@pytest.fixture
def requests() -> list[str]:
    return []


@pytest.fixture
def offline_window(qtbot, services, event_bus, theme_manager, requests) -> MainWindow:
    """A window whose update check gets a newer release without touching the network."""

    def fetch(url):
        requests.append(url)
        return NEWER

    with_fake_updates = dataclasses.replace(services, updates=UpdateService("0.2.0", fetch))
    window = MainWindow(with_fake_updates, event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()
    return window


def count(window) -> str:
    label = window.top_bar.notification_count
    return label.text() if label.isVisible() else ""


def found_release(qtbot, window) -> None:
    window.check_for_updates()
    qtbot.waitUntil(lambda: count(window) == "1")


def test_starts_without_notifications_or_requests(offline_window, requests):
    assert count(offline_window) == ""
    assert requests == []


def test_newer_release_is_counted_and_listed(qtbot, offline_window):
    found_release(qtbot, offline_window)

    offline_window.top_bar.notifications_button.click()

    panel = offline_window.notification_panel
    assert panel.isVisible()
    assert [n.kind for n in offline_window.notices()] == [NoticeKind.UPDATE]
    assert "9.0.0" in offline_window.notices()[0].title
    assert panel.rows[0].action_button.text() == "Descargar"


def test_download_opens_the_release_page(qtbot, offline_window, monkeypatch):
    opened = []
    monkeypatch.setattr(
        main_window_module.QDesktopServices, "openUrl", lambda url: opened.append(url.toString())
    )
    found_release(qtbot, offline_window)
    offline_window.open_notifications()

    offline_window.notification_panel.rows[0].action_button.click()

    assert opened == ["https://example.com/v9"]
    assert not offline_window.notification_panel.isVisible()


def test_dismissed_release_is_not_announced_again(qtbot, services, offline_window):
    found_release(qtbot, offline_window)
    offline_window.open_notifications()

    offline_window.notification_panel.rows[0].dismiss_button.click()

    assert count(offline_window) == ""
    assert services.settings.dismissed_version() == "9.0.0"


def test_no_check_when_turned_off(services, offline_window, requests):
    services.settings.set_check_updates(False)

    offline_window.check_for_updates()

    assert requests == []
    assert count(offline_window) == ""


def test_stale_rate_notice_leads_to_settings(qtbot, services, event_bus, offline_window, dollars):
    services.exchange_rates.set_rate(date.today() - timedelta(days=10), Decimal("1000"))
    event_bus.exchange_rates_changed.emit()
    assert count(offline_window) == "1"
    offline_window.open_notifications()

    offline_window.notification_panel.rows[0].action_button.click()

    assert offline_window.current_page is offline_window.page(PageId.SETTINGS)


def test_empty_panel_says_so(qtbot, offline_window):
    offline_window.open_notifications()

    assert offline_window.notification_panel.rows == []


def test_gear_opens_settings(offline_window):
    offline_window.top_bar.settings_button.click()

    assert offline_window.current_page is offline_window.page(PageId.SETTINGS)


def test_charges_notice_follows_payments_and_leads_to_the_charges(
    qtbot, services, event_bus, offline_window, pesos
):
    charge = services.recurring.create(
        charge_draft(services, pesos.id, ars("100"), date.today(), name="Netflix")
    )
    event_bus.recurring_changed.emit()
    assert count(offline_window) == "1"
    offline_window.open_notifications()

    offline_window.notification_panel.rows[0].action_button.click()
    assert offline_window.current_page is offline_window.page(PageId.RECURRING)

    services.recurring.pay(charge.id, ars("100"), date.today(), pesos.id)
    event_bus.recurring_changed.emit()
    assert not offline_window.top_bar.notification_count.isVisibleTo(offline_window)
