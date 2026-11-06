from decimal import Decimal

import pytest
from factories import TODAY, ars, expense_draft, usd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.navigation import PageId
from nodus.ui.pages import accounts_page
from nodus.ui.pages.accounts_page import AccountRow, AccountsPage


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> AccountsPage:
    accounts_page = AccountsPage(services, event_bus, theme_manager)
    qtbot.addWidget(accounts_page)
    accounts_page.refresh()
    return accounts_page


def texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def rows(page) -> list[AccountRow]:
    """Current rows; rows of a replaced card linger hidden until Qt deletes them."""
    return [row for row in page.findChildren(AccountRow) if row.isVisibleTo(page)]


class TestAccountDialog:
    def make(self, qtbot, services, event_bus, account=None) -> AccountDialog:
        dialog = AccountDialog(services, event_bus, account)
        qtbot.addWidget(dialog)
        return dialog

    def test_creates_account_and_announces_it(self, qtbot, services, event_bus):
        dialog = self.make(qtbot, services, event_bus)
        dialog.name_input.setText("Dólares")
        dialog.type_input.setCurrentIndex(dialog.type_input.findData(AccountType.SAVINGS))
        dialog.currency_input.setCurrentIndex(dialog.currency_input.findData(Currency.USD))
        dialog.balance_input.line_edit.setText("1.500,50")

        with qtbot.waitSignal(event_bus.accounts_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        [account] = services.accounts.list_accounts()
        assert (account.name, account.type, account.initial_balance) == (
            "Dólares", AccountType.SAVINGS, usd("1500.50"),
        )  # fmt: skip
        assert dialog.result() == AccountDialog.DialogCode.Accepted

    def test_validation_error_is_shown_and_dialog_stays_open(self, qtbot, services, event_bus):
        dialog = self.make(qtbot, services, event_bus)
        dialog.show()
        dialog.balance_input.line_edit.setText("100")

        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert dialog.isVisible()
        assert dialog.error_label.text() == "El nombre no puede estar vacío."
        assert services.accounts.list_accounts() == []

    def test_invalid_amount_is_reported(self, qtbot, services, event_bus):
        dialog = self.make(qtbot, services, event_bus)
        dialog.name_input.setText("Caja")
        dialog.balance_input.line_edit.setText("mil")

        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert "no es un monto válido" in dialog.error_label.text()

    def test_edit_loads_values_and_locks_currency(self, qtbot, services, event_bus, dollars):
        dialog = self.make(qtbot, services, event_bus, dollars)

        assert dialog.name_input.text() == "Ahorro"
        assert dialog.balance_input.line_edit.text() == "500,00"
        assert not dialog.currency_input.isEnabled()

        dialog.name_input.setText("Ahorro MEP")
        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert services.accounts.get(dollars.id).name == "Ahorro MEP"


class TestAccountsPage:
    def test_empty_state(self, page):
        assert "Todavía no hay cuentas" in texts(page)

    def test_lists_accounts_and_net_worth(self, services, page, pesos, dollars):
        services.exchange_rates.set_rate(TODAY, Decimal("1000"))

        page.refresh()

        assert [row.account.name for row in rows(page)] == ["Ahorro", "Banco"]
        card = page.net_worth_card
        assert card.total_label.text() == "$ 600.000,00"
        assert card.legends[Currency.ARS].amount.text() == "$ 100.000,00"
        assert card.legends[Currency.USD].amount.text() == "US$ 500,00"
        assert [card.legends[c].share.text() for c in Currency] == ["17 %", "83 %"]
        assert card.rate_label.text() == f"US$ 1 = $ 1.000,00 · {TODAY:%d/%m}"

        card.currency_input.set_index(1)

        assert card.total_label.text() == "US$ 600,00"
        assert services.settings.net_worth_currency() is Currency.USD

    def test_shows_missing_rate_instead_of_inventing_totals(self, page, pesos, dollars):
        page.refresh()

        card = page.net_worth_card
        assert card.missing_rate.isVisibleTo(page) and not card.total_label.isVisibleTo(page)
        assert card.subtotal_labels[Currency.ARS].text() == "$ 100.000,00"
        assert card.subtotal_labels[Currency.USD].text() == "US$ 500,00"
        assert card.rate_label.text() == "Sin cotización"

    def test_load_rate_leads_to_settings(self, qtbot, page, pesos, dollars):
        page.refresh()

        with qtbot.waitSignal(page.navigate_requested) as navigation:
            page.net_worth_card.load_rate_button.click()

        assert navigation.args == [PageId.SETTINGS]

    def test_archive_moves_account_to_archived_section(
        self, qtbot, services, event_bus, page, pesos, dollars
    ):
        page.refresh()
        row = next(r for r in rows(page) if r.account.id == dollars.id)

        qtbot.mouseClick(row.archive_button, Qt.MouseButton.LeftButton)

        assert services.accounts.get(dollars.id).is_archived
        assert "ARCHIVADAS" in texts(page)
        archived_row = next(r for r in rows(page) if r.account.id == dollars.id)
        assert archived_row.archive_button.text() == "Desarchivar"

    def test_refreshes_when_accounts_change(self, services, event_bus, page):
        services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("10"))

        event_bus.accounts_changed.emit()

        assert [row.account.name for row in rows(page)] == ["Efectivo"]

    def test_delete_after_confirmation_warns_about_movements(
        self, qtbot, monkeypatch, services, event_bus, page, pesos
    ):
        services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        page.refresh()
        warnings = []
        monkeypatch.setattr(
            accounts_page, "confirm", lambda _parent, _title, text: warnings.append(text) or True
        )

        with qtbot.waitSignal(event_bus.accounts_changed):
            qtbot.mouseClick(rows(page)[0].delete_button, Qt.MouseButton.LeftButton)

        assert warnings == [
            "Se va a eliminar la cuenta «Banco». Su única transacción también se elimina."
            " Para conservar el historial, archívala en su lugar."
        ]
        assert services.accounts.list_accounts(include_archived=True) == []

    def test_delete_is_cancelled_when_not_confirmed(
        self, qtbot, monkeypatch, services, page, pesos
    ):
        page.refresh()
        monkeypatch.setattr(accounts_page, "confirm", lambda *_args: False)

        qtbot.mouseClick(rows(page)[0].delete_button, Qt.MouseButton.LeftButton)

        assert services.accounts.list_accounts() == [pesos]


@pytest.fixture
def investment(services):
    return services.accounts.create(
        "MP Inversiones", AccountType.INVESTMENT, Currency.ARS, ars("1000000")
    )


class TestValueAdjustment:
    def make(self, qtbot, services, event_bus, account) -> ValueAdjustmentDialog:
        dialog = ValueAdjustmentDialog(services, event_bus, account, today=TODAY)
        qtbot.addWidget(dialog)
        return dialog

    def test_only_savings_and_investments_offer_it(self, page, event_bus, pesos, investment):
        event_bus.accounts_changed.emit()

        offered = {row.account.name: row.value_button.isVisibleTo(row) for row in rows(page)}

        assert offered == {"Banco": False, "MP Inversiones": True}

    def test_shows_the_difference_and_saves_it_as_gain(
        self, qtbot, services, event_bus, investment
    ):
        dialog = self.make(qtbot, services, event_bus, investment)
        assert dialog.value_input.money() == ars("1000000")

        dialog.value_input.line_edit.setText("1.012.300")

        assert dialog.difference_label.text() == "Ganancia: +$ 12.300,00"
        with qtbot.waitSignal(event_bus.accounts_changed):
            dialog.save_button.click()
        assert services.accounts.balance(investment.id) == ars("1012300")

    def test_row_shows_the_gain(self, page, services, event_bus, investment):
        services.accounts.adjust_value(investment.id, ars("1012300"), TODAY)
        event_bus.accounts_changed.emit()

        assert "Inversión · ARS · Rendimiento +$ 12.300,00" in texts(page)

    def test_undo_removes_the_last_adjustment(self, qtbot, services, event_bus, investment):
        services.accounts.adjust_value(investment.id, ars("1012300"), TODAY)
        dialog = self.make(qtbot, services, event_bus, investment)

        dialog.undo_button.click()

        assert services.accounts.balance(investment.id) == ars("1000000")
