import dataclasses
import json
from datetime import date

import pytest
from PySide6.QtWidgets import QPushButton

from nodus.links import DONATE_URL, feedback_url
from nodus.services.changelog import ChangelogEntry
from nodus.services.news_service import NewsService
from nodus.services.update_service import Release, UpdateService
from nodus.ui import browser
from nodus.ui.dialogs.news_dialog import NewsDialog, entries_markdown
from nodus.ui.main_window import MainWindow
from nodus.ui.navigation import PageId
from nodus.ui.pages.settings_page import SettingsPage

ENTRIES = [
    ChangelogEntry("1.1.0", date(2026, 11, 7), "- Euros y pesos chilenos."),
    ChangelogEntry("1.0.1", date(2026, 11, 6), "- «Editar» en los filtros."),
]
RELEASE = Release("9.0.0", "https://example.com/v9", "- Algo nuevo.")


@pytest.fixture
def opened(monkeypatch) -> list[NewsDialog]:
    """The news dialogs that would have opened, without blocking the test."""
    dialogs: list[NewsDialog] = []
    monkeypatch.setattr(NewsDialog, "exec", lambda dialog: dialogs.append(dialog))
    return dialogs


def with_news(services, last_seen: str | None) -> object:
    if last_seen is not None:
        services.settings.set_last_seen_version(last_seen)
    news = NewsService(services.settings, "1.1.0", False, lambda: ENTRIES)
    return dataclasses.replace(services, news=news)


def test_entries_are_written_under_their_version_and_date():
    markdown = entries_markdown(ENTRIES)

    assert markdown.index("### Nodus 1.1.0 · 07/11/2026") < markdown.index("### Nodus 1.0.1")
    assert "- Euros y pesos chilenos." in markdown


def test_installed_news_only_close(qtbot):
    dialog = NewsDialog.for_entries(ENTRIES)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Novedades de Nodus"
    assert dialog.download_button is None
    assert "Euros y pesos chilenos" in dialog.text.toPlainText()


def test_release_news_download_opens_its_page(qtbot, monkeypatch):
    urls = []
    monkeypatch.setattr(
        browser.QDesktopServices, "openUrl", lambda url: urls.append(url.toString())
    )
    dialog = NewsDialog.for_release(RELEASE)
    qtbot.addWidget(dialog)

    dialog.download_button.click()

    assert urls == ["https://example.com/v9"]


def test_window_shows_unseen_news_once(qtbot, services, event_bus, theme_manager, opened):
    window = MainWindow(with_news(services, "1.0.1"), event_bus, theme_manager)
    qtbot.addWidget(window)

    window.show_unseen_news()
    window.show_unseen_news()

    assert len(opened) == 1
    assert "Euros" in opened[0].text.toPlainText()
    assert "Editar" not in opened[0].text.toPlainText()


def test_window_shows_nothing_when_already_seen(qtbot, services, event_bus, theme_manager, opened):
    window = MainWindow(with_news(services, "1.1.0"), event_bus, theme_manager)
    qtbot.addWidget(window)

    window.show_unseen_news()

    assert opened == []


def test_update_notice_tells_what_the_release_brings(
    qtbot, services, event_bus, theme_manager, opened
):
    answer = {"tag_name": "v9.0.0", "html_url": RELEASE.url, "body": "Nodus 9.0.0\n\n- Algo."}
    updates = UpdateService("0.2.0", lambda _url: json.dumps(answer).encode())
    window = MainWindow(dataclasses.replace(services, updates=updates), event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()
    window.check_for_updates()
    qtbot.waitUntil(lambda: window.top_bar.notification_count.isVisible())
    window.open_notifications()

    window.notification_panel.rows[0].news_button.click()

    assert opened[0].windowTitle() == "Qué trae Nodus 9.0.0"
    assert opened[0].text.toPlainText().strip() == "Algo."
    assert opened[0].download_button is not None


def test_update_notice_without_notes_has_no_news_button(qtbot, services, event_bus, theme_manager):
    answer = {"tag_name": "v9.0.0", "html_url": RELEASE.url}
    updates = UpdateService("0.2.0", lambda _url: json.dumps(answer).encode())
    window = MainWindow(dataclasses.replace(services, updates=updates), event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()
    window.check_for_updates()
    qtbot.waitUntil(lambda: window.top_bar.notification_count.isVisible())
    window.open_notifications()

    assert window.notification_panel.rows[0].news_button is None


def test_settings_opens_every_version(qtbot, services, event_bus, theme_manager, opened):
    page = SettingsPage(with_news(services, None), event_bus, theme_manager)
    qtbot.addWidget(page)

    page.show_news()

    text = opened[0].text.toPlainText()
    assert "Euros" in text and "Editar" in text


def test_feedback_and_support_open_their_pages(window, monkeypatch):
    urls = []
    monkeypatch.setattr(
        browser.QDesktopServices, "openUrl", lambda url: urls.append(url.toString())
    )

    window.top_bar.feedback_button.click()
    page = window.page(PageId.SETTINGS)
    buttons = {b.text(): b for b in page.findChildren(QPushButton)}
    buttons["Enviar comentarios"].click()
    buttons["Invitar un cafecito"].click()

    assert urls == [feedback_url(), feedback_url(), DONATE_URL]
