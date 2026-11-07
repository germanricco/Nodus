from datetime import date
from decimal import Decimal

import pytest
from factories import ars, eur, expense_draft

from nodus.models.account import AccountType
from nodus.models.currency import FOREIGN_CURRENCIES, Currency
from nodus.ui.dialogs import export
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
    assert page.current_rate_label.text() == "US$ 1 = $ 1.215,50"
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


def test_about_card_turns_update_check_off(services, page):
    assert page.check_updates_input.isChecked()

    page.check_updates_input.click()

    assert not services.settings.check_updates()


def test_backup_now_creates_a_copy_and_shows_it(services, page):
    page.backup_now_button.click()

    assert services.backups.last_backup() == date.today()
    assert page.backup_row.detail.text() == f"Última: {date.today():%d/%m/%Y}"


def test_failed_daily_backup_is_shown(services, page):
    services.backups.last_error = "No se pudo hacer la copia del día: disco lleno"

    page.refresh()

    assert "disco lleno" in page.backup_row.detail.text()


def test_restore_replaces_data_and_announces_it(
    monkeypatch, qtbot, services, event_bus, page, pesos
):
    backup = services.backups.create(date(2026, 11, 1))
    services.accounts.delete(pesos.id)
    monkeypatch.setattr(settings_page.QFileDialog, "getOpenFileName", lambda *_a: (str(backup), ""))
    monkeypatch.setattr(settings_page, "confirm", lambda *_a, **_k: True)
    monkeypatch.setattr(settings_page.QMessageBox, "information", lambda *_a: None)

    with qtbot.waitSignal(event_bus.accounts_changed):
        page.restore_button.click()

    assert [a.name for a in services.accounts.list_accounts()] == ["Banco"]


def test_restore_of_an_invalid_file_warns_and_keeps_data(
    monkeypatch, tmp_path, services, page, pesos
):
    bogus = tmp_path / "bogus.db"
    bogus.write_bytes(b"no soy una base")
    warnings = []
    monkeypatch.setattr(settings_page.QFileDialog, "getOpenFileName", lambda *_a: (str(bogus), ""))
    monkeypatch.setattr(settings_page, "confirm", lambda *_a, **_k: True)
    monkeypatch.setattr(settings_page.QMessageBox, "warning", lambda *a: warnings.append(a[2]))

    page.restore_button.click()

    assert warnings == ["El archivo no es una copia válida de Nodus."]
    assert [a.name for a in services.accounts.list_accounts()] == ["Banco"]


def test_restore_cancelled_in_the_file_dialog_does_nothing(monkeypatch, services, page, pesos):
    monkeypatch.setattr(settings_page.QFileDialog, "getOpenFileName", lambda *_a: ("", ""))

    page.restore_button.click()

    assert [a.name for a in services.accounts.list_accounts()] == ["Banco"]


def test_export_all_writes_every_transaction(monkeypatch, tmp_path, services, page, pesos):
    services.transactions.create(expense_draft(services, pesos.id, ars("10"), date(2020, 1, 1)))
    services.transactions.create(expense_draft(services, pesos.id, ars("20"), date(2026, 11, 1)))
    target = tmp_path / "todo.csv"
    monkeypatch.setattr(export.QFileDialog, "getSaveFileName", lambda *_a: (str(target), ""))

    page.export_all_button.click()

    assert target.read_text(encoding="utf-8-sig").count("\n") == 3


class TestOtherCurrencies:
    def test_with_only_the_dollar_there_is_no_currency_to_choose(self, page):
        assert not page.rate_currency_row.isVisibleTo(page)
        assert page.rate_currency() is Currency.USD

    def test_euro_rates_are_kept_apart_from_the_dollar(self, qtbot, services, event_bus, page):
        services.accounts.create("Europa", AccountType.CASH, Currency.EUR, eur("100"))
        services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1200"))
        page.refresh()
        assert page.rate_currency_row.isVisibleTo(page)
        clp_segment = page.rate_currency_input.buttons[FOREIGN_CURRENCIES.index(Currency.CLP)]
        assert not clp_segment.isEnabled()

        page.rate_currency_input.set_index(FOREIGN_CURRENCIES.index(Currency.EUR))
        assert rate_rows(page) == []
        assert page.rate_unit_label.text() == "€ 1 ="
        assert page.rate_value_input.line_edit.placeholderText() == "Pesos por euro"
        page.rate_value_input.line_edit.setText("1.738,25")
        with qtbot.waitSignal(event_bus.exchange_rates_changed):
            page.save_rate_button.click()

        assert services.exchange_rates.rate_on(date.today(), Currency.EUR).rate == Decimal(
            "1738.25"
        )
        assert page.current_rate_label.text() == "€ 1 = $ 1.738,25"
        assert [row.rate.rate for row in rate_rows(page)] == [Decimal("1738.25")]
