from datetime import date
from decimal import Decimal

import pytest

from nodus.ui.pages import settings_page
from nodus.ui.pages.settings_page import THEME_MODES, RateRow, SettingsPage
from nodus.ui.theme.theme import ThemeMode


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> SettingsPage:
    settings = SettingsPage(services, event_bus, theme_manager)
    qtbot.addWidget(settings)
    settings.refresh()
    return settings


def rate_rows(page) -> list[RateRow]:
    return [row for row in page.findChildren(RateRow) if row.isVisibleTo(page)]


def test_choosing_theme_applies_and_saves_it(services, theme_manager, page):
    page.theme_input.set_index(THEME_MODES.index(ThemeMode.DARK))

    assert theme_manager.mode is ThemeMode.DARK
    assert services.settings.theme_preference() == "dark"


def test_saving_rate_adds_it_to_history(qtbot, services, event_bus, page):
    page.rate_value_input.line_edit.setText("1.215,50")

    with qtbot.waitSignal(event_bus.exchange_rates_changed):
        page.save_rate_button.click()

    assert services.exchange_rates.rate_on(date.today()).rate == Decimal("1215.50")
    assert [row.rate.rate for row in rate_rows(page)] == [Decimal("1215.50")]
    assert page.current_rate_label.text().startswith("Vigente hoy: US$ 1 = $ 1.215,50")
    assert page.rate_value_input.line_edit.text() == ""


def test_invalid_rate_shows_error(services, page):
    page.rate_value_input.line_edit.setText("0")

    page.save_rate_button.click()

    assert page.rate_error_label.text() == "La cotización debe ser mayor que cero."
    assert services.exchange_rates.history() == []


def test_delete_rate_after_confirmation(monkeypatch, services, page):
    services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1200"))
    page.refresh()
    monkeypatch.setattr(settings_page, "confirm", lambda *_args: True)

    rate_rows(page)[0].delete_button.click()

    assert services.exchange_rates.history() == []


def test_shows_data_file(services, page):
    assert page.data_path_label.text() == str(services.settings.data_file)
