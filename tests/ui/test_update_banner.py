import dataclasses
import json

import pytest

from nodus.services.update_service import UpdateService
from nodus.ui.main_window import MainWindow

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


def test_banner_starts_hidden(offline_window, requests):
    assert not offline_window.update_banner.isVisible()
    assert requests == []


def test_newer_release_shows_banner(qtbot, offline_window):
    offline_window.check_for_updates()

    qtbot.waitUntil(offline_window.update_banner.isVisible)
    assert "9.0.0" in offline_window.update_banner.message_label.text()


def test_closing_hides_banner(qtbot, offline_window):
    offline_window.check_for_updates()
    qtbot.waitUntil(offline_window.update_banner.isVisible)

    offline_window.update_banner.close_button.click()

    assert not offline_window.update_banner.isVisible()


def test_no_check_when_turned_off(services, offline_window, requests):
    services.settings.set_check_updates(False)

    offline_window.check_for_updates()

    assert requests == []
    assert not offline_window.update_banner.isVisible()
