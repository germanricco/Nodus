import dataclasses
from datetime import date
from decimal import Decimal

import pytest
from factories import FakeRegistry, ars, eur, expense_draft
from menus import run_action

from nodus.models.account import AccountType
from nodus.models.currency import FOREIGN_CURRENCIES, Currency
from nodus.services.errors import BackupError
from nodus.services.startup_service import StartupService
from nodus.ui.dialogs import export, external_backup
from nodus.ui.pages import settings_page
from nodus.ui.pages.settings_page import THEME_MODES, RateRow, SettingsPage
from nodus.ui.theme.design import Motion, motion_ms, set_reduced_motion
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

    run_action(rate_rows(page)[0].actions(), "Eliminar")

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


def test_failed_backup_now_warns_the_user(services, page, monkeypatch):
    def broken(_today):
        raise BackupError("disco lleno")

    warnings = []
    monkeypatch.setattr(services.backups, "create", broken)
    monkeypatch.setattr(
        settings_page.QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text)
    )

    page.backup_now_button.click()

    assert warnings == ["No se pudo copiar: disco lleno"]


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
        assert not clp_segment.isVisibleTo(page)

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


class TestStartWithWindows:
    def test_from_the_source_code_it_is_disabled_and_says_why(self, page):
        assert not page.startup_input.isEnabled()
        assert page.startup_input.toolTip() == "Disponible en la versión instalada"

    def test_ticking_it_registers_nodus(self, qtbot, services, event_bus, theme_manager):
        registry = FakeRegistry()
        installed = dataclasses.replace(
            services, startup=StartupService(registry, r"C:\Nodus\Nodus.exe")
        )
        settings = SettingsPage(installed, event_bus, theme_manager)
        qtbot.addWidget(settings)
        settings.refresh()
        assert settings.startup_input.isEnabled() and not settings.startup_input.isChecked()

        settings.startup_input.click()

        assert registry.value == r'"C:\Nodus\Nodus.exe"'
        settings.startup_input.click()
        assert registry.value is None


def test_reduce_motion_is_saved_and_applied_at_once(services, page):
    services.settings.set_reduce_motion(False)
    set_reduced_motion(False)
    page.refresh()
    assert not page.reduce_motion_input.isChecked()

    page.reduce_motion_input.click()

    assert services.settings.reduce_motion()
    assert motion_ms(Motion.SLOW) == 0

    page.reduce_motion_input.click()

    assert not services.settings.reduce_motion()
    assert motion_ms(Motion.SLOW) == Motion.SLOW


class TestCopyOutside:
    def test_says_there_is_none_yet(self, page):
        assert page.outside_row.detail.text().startswith("Nunca.")
        assert page.backup_reminder_input.isChecked()

    def test_saves_in_the_chosen_folder(self, monkeypatch, tmp_path, services, page):
        monkeypatch.setattr(
            external_backup.QFileDialog, "getExistingDirectory", lambda *_a: str(tmp_path)
        )
        told = []
        monkeypatch.setattr(
            external_backup.QMessageBox, "information", lambda *a: told.append(a[2])
        )

        page.save_outside_button.click()

        assert (tmp_path / f"nodus-{date.today()}.db").is_file()
        assert told == [f"Se guardó «nodus-{date.today()}.db» en {tmp_path}."]
        assert page.outside_row.detail.text() == f"Última: {date.today():%d/%m/%Y}"

    def test_offers_the_folder_of_the_last_time(self, monkeypatch, tmp_path, services, page):
        services.backups.export_to(tmp_path, date(2026, 10, 31))
        asked = []
        monkeypatch.setattr(
            external_backup.QFileDialog,
            "getExistingDirectory",
            lambda *a: asked.append(a) or "",
        )
        monkeypatch.setattr(external_backup.QMessageBox, "exec", lambda _box: 0)
        monkeypatch.setattr(
            external_backup.QMessageBox, "clickedButton", lambda box: box.defaultButton()
        )

        assert external_backup.choose_folder(page, services) == tmp_path
        assert asked == []

    def test_cancelled_saves_nothing(self, monkeypatch, services, page):
        monkeypatch.setattr(external_backup.QFileDialog, "getExistingDirectory", lambda *_a: "")

        page.save_outside_button.click()

        assert services.backups.last_external_backup() is None

    def test_reminder_can_be_turned_off(self, services, page):
        page.backup_reminder_input.click()

        assert services.settings.backup_reminder() is False
