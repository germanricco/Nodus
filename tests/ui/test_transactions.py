from datetime import date

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd
from PySide6.QtCore import Qt

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.services.transaction_service import TransferDraft
from nodus.ui import main_window as main_window_module
from nodus.ui.dialogs.transaction_dialog import (
    EXPENSE_MODE,
    INCOME_MODE,
    TRANSFER_MODE,
    TransactionDialog,
)
from nodus.ui.navigation import PageId
from nodus.ui.pages import transactions_page
from nodus.ui.pages.transactions_page import AMOUNT, CATEGORY, TransactionsPage

EXPENSE = TransactionType.EXPENSE
NOVEMBER = Month(2026, 11)


def make_dialog(qtbot, services, event_bus, transaction=None) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, transaction)
    qtbot.addWidget(dialog)
    return dialog


def save(qtbot, dialog) -> None:
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)


def all_transactions(services):
    return services.transactions.list_transactions(TransactionFilter())


def buy_dollars(services, pesos, dollars):
    return services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("121550"), date(2026, 11, 4), amount_in=usd("100"))
    )


class TestTransactionDialog:
    def test_records_expense_in_chosen_category(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("1.500,50")
        dialog.category_input.select(category_id(services, "Ocio", EXPENSE))
        dialog.note_input.setText("Cine")

        with qtbot.waitSignal(event_bus.transactions_changed):
            save(qtbot, dialog)

        [saved] = all_transactions(services)
        assert saved.type is EXPENSE
        assert saved.amount == ars("1500.50")
        assert saved.category_id == category_id(services, "Ocio", EXPENSE)
        assert saved.note == "Cine"
        assert saved.occurred_on == date.today()

    def test_category_choices_follow_mode(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)

        dialog.mode_input.set_index(INCOME_MODE)

        names = [
            dialog.category_input.itemText(i).strip() for i in range(dialog.category_input.count())
        ]
        assert names == ["Reembolsos", "Sueldo", "Trabajo freelance", "Otros"]

    def test_transfer_between_currencies_shows_implied_rate(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.mode_input.set_index(TRANSFER_MODE)
        dialog.account_input.select(pesos.id)
        dialog.to_account_input.select(dollars.id)
        dialog.amount_input.line_edit.setText("121.550")
        dialog.amount_in_input.line_edit.setText("100")

        assert dialog.amount_in_input.isVisibleTo(dialog)
        assert not dialog.category_input.isVisibleTo(dialog)
        assert dialog.rate_hint.text() == "Cotización implícita: US$ 1 = $ 1.215,50"

        save(qtbot, dialog)

        [outgoing] = services.transactions.list_transactions(TransactionFilter(account_id=pesos.id))
        transfer = services.transactions.get_transfer(outgoing.transfer_id)
        assert transfer.incoming.amount == usd("100")

    def test_new_transfer_starts_with_a_different_destination(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        dialog = make_dialog(qtbot, services, event_bus)

        dialog.mode_input.set_index(TRANSFER_MODE)

        assert dialog.account_input.current_id() != dialog.to_account_input.current_id()

    def test_same_currency_transfer_hides_incoming_amount(self, qtbot, services, event_bus, pesos):
        services.accounts.create("Efectivo", pesos.type, pesos.currency, ars("0"))
        dialog = make_dialog(qtbot, services, event_bus)

        dialog.mode_input.set_index(TRANSFER_MODE)

        assert not dialog.amount_in_input.isVisibleTo(dialog)

    def test_editing_transfer_locks_mode_and_updates_both_legs(
        self, qtbot, services, event_bus, pesos, dollars
    ):
        transfer = buy_dollars(services, pesos, dollars)
        dialog = make_dialog(qtbot, services, event_bus, transfer.incoming)

        assert dialog.mode_input.index() == TRANSFER_MODE
        assert not dialog.mode_input.buttons[EXPENSE_MODE].isEnabled()
        assert dialog.account_input.current_id() == pesos.id
        assert dialog.amount_in_input.money() == usd("100")

        dialog.amount_in_input.line_edit.setText("101")
        save(qtbot, dialog)

        assert services.transactions.get_transfer(transfer.id).incoming.amount == usd("101")
        assert len(all_transactions(services)) == 2

    def test_editing_expense_keeps_category_and_can_become_income(
        self, qtbot, services, event_bus, pesos
    ):
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        dialog = make_dialog(qtbot, services, event_bus, expense)

        assert dialog.category_input.current_id() == expense.category_id
        assert not dialog.mode_input.buttons[TRANSFER_MODE].isEnabled()

        dialog.mode_input.set_index(INCOME_MODE)
        save(qtbot, dialog)

        assert services.transactions.get(expense.id).type is TransactionType.INCOME

    def test_invalid_amount_keeps_dialog_open_with_error(self, qtbot, services, event_bus, pesos):
        dialog = make_dialog(qtbot, services, event_bus)
        dialog.amount_input.line_edit.setText("0")

        save(qtbot, dialog)

        assert dialog.error_label.text() == "El monto debe ser mayor que cero."
        assert all_transactions(services) == []


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> TransactionsPage:
    transactions = TransactionsPage(services, event_bus, theme_manager)
    qtbot.addWidget(transactions)
    transactions.month_selector.set_month(NOVEMBER)
    transactions.refresh()
    return transactions


def column(page, index: int) -> list[str]:
    model = page.model
    return [model.data(model.index(row, index)) for row in range(model.rowCount())]


def populate(services, pesos, dollars) -> None:
    services.transactions.create(
        expense_draft(services, pesos.id, ars("2500"), occurred_on=date(2026, 11, 2), note="Pizza")
    )
    services.transactions.create(
        income_draft(services, pesos.id, ars("900000"), occurred_on=date(2026, 11, 1))
    )
    services.transactions.create(
        expense_draft(services, pesos.id, ars("99"), occurred_on=date(2026, 10, 31), note="Viejo")
    )
    buy_dollars(services, pesos, dollars)


class TestTransactionsPage:
    def test_lists_month_newest_first_with_transfer_as_one_row(
        self, services, page, pesos, dollars
    ):
        populate(services, pesos, dollars)

        page.refresh()

        assert column(page, AMOUNT) == ["$ 121.550,00 → US$ 100,00", "-$ 2.500,00", "$ 900.000,00"]
        assert column(page, CATEGORY)[0] == "Transferencia"
        assert page.model.item(0).account_text == "Banco → Ahorro"

    def test_filters_by_type_text_and_month(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()

        page.type_filter.setCurrentText("Gastos")
        assert column(page, AMOUNT) == ["-$ 2.500,00"]

        page.type_filter.setCurrentText("Todos los tipos")
        page.search_input.setText("viejo")
        assert column(page, AMOUNT) == []
        assert page.empty_label.isVisibleTo(page)

        page.month_selector.set_month(NOVEMBER.previous())
        assert column(page, AMOUNT) == ["-$ 99,00"]

    def test_clear_filters_keeps_month_and_shows_everything(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()
        assert not page.clear_filters_button.isEnabled()
        page.account_filter.select(dollars.id)
        page.type_filter.setCurrentText("Transferencias")
        page.search_input.setText("nada")
        assert page.clear_filters_button.isEnabled()

        page.clear_filters_button.click()

        assert page.current_filter() == TransactionFilter(start=NOVEMBER.start, end=NOVEMBER.end)
        assert len(column(page, AMOUNT)) == 3
        assert not page.clear_filters_button.isEnabled()

    def test_account_filter_still_shows_both_ends_of_transfer(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()

        page.account_filter.select(dollars.id)

        assert column(page, AMOUNT) == ["$ 121.550,00 → US$ 100,00"]

    def test_delete_transfer_after_confirmation(
        self, qtbot, monkeypatch, services, event_bus, page, pesos, dollars
    ):
        buy_dollars(services, pesos, dollars)
        page.refresh()
        monkeypatch.setattr(transactions_page, "confirm", lambda *_args: True)
        page.table.selectRow(0)

        with qtbot.waitSignal(event_bus.transactions_changed):
            page.delete_button.click()

        assert all_transactions(services) == []
        assert page.model.rowCount() == 0

    def test_actions_need_a_selection(self, services, page, pesos, dollars):
        populate(services, pesos, dollars)
        page.refresh()

        assert not page.delete_button.isEnabled()
        page.table.selectRow(1)
        assert page.delete_button.isEnabled()


class TestAddTransactionButton:
    def test_without_accounts_leads_to_accounts_page(self, monkeypatch, window):
        messages = []
        monkeypatch.setattr(
            main_window_module.QMessageBox, "information", lambda *args: messages.append(args)
        )

        window.top_bar.add_transaction_requested.emit()

        assert len(messages) == 1
        assert window.current_page is window.page(PageId.ACCOUNTS)

    def test_with_accounts_opens_dialog(self, monkeypatch, window, pesos):
        opened = []
        monkeypatch.setattr(TransactionDialog, "exec", lambda dialog: opened.append(dialog))

        window.top_bar.add_transaction_requested.emit()

        assert len(opened) == 1
