"""Recording again what repeats without being a recurring payment: «Duplicar» in a
movement's menu and «Repetir el último gasto» in Ctrl+K."""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pytest
from factories import ars, expense_draft, in_view, light_theme, usd
from menus import run_action, texts
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from nodus.models.installment_plan import InstallmentPlan
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.transactions.transfer_service import TransferDraft
from nodus.ui.dialogs.transaction_dialog import (
    EXPENSE_MODE,
    TRANSFER_MODE,
    TransactionDialog,
    TransactionStart,
)
from nodus.ui.pages.transactions_page import TransactionsPage

TODAY = date.today()
LAST_WEEK = TODAY - timedelta(days=7)


def copy_form(qtbot, services, event_bus, original) -> TransactionDialog:
    dialog = TransactionDialog(
        services, event_bus, light_theme(), start=TransactionStart(copy_of=original)
    )
    qtbot.addWidget(dialog)
    return dialog


def all_transactions(services):
    return services.transactions.list_transactions(TransactionFilter())


@pytest.fixture
def cafe(services, pesos):
    draft = expense_draft(services, pesos.id, ars("2500"), LAST_WEEK, note="Café con medialunas")
    draft = dataclasses.replace(draft, payee_name="La Esquina", tag_names=("Salidas",))
    return services.transactions.create(draft)


def test_a_copy_has_everything_but_the_day_and_saves_as_a_new_movement(
    qtbot, services, event_bus, cafe
):
    dialog = copy_form(qtbot, services, event_bus, cafe)

    assert dialog.windowTitle() == "Nueva transacción"
    assert dialog.mode_input.index() == EXPENSE_MODE
    assert dialog.account_input.current_id() == cafe.account_id
    assert dialog.amount_input.money() == ars("2500")
    assert dialog.category_input.current_id() == cafe.category_id
    assert dialog.payee_input.text() == "La Esquina"
    assert dialog.tag_input.names() == ("Salidas",)
    assert dialog.note_input.text() == "Café con medialunas"
    assert dialog.date_input.day() == TODAY

    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    saved = all_transactions(services)
    assert len(saved) == 2
    copy = next(t for t in saved if t.id != cafe.id)
    assert (copy.occurred_on, copy.amount, copy.payee_id) == (TODAY, cafe.amount, cafe.payee_id)


def test_a_transfer_copies_both_accounts_and_amounts(qtbot, services, event_bus, pesos, dollars):
    transfer = services.transfers.create(
        TransferDraft(pesos.id, dollars.id, ars("120000"), LAST_WEEK, usd("100"))
    )

    dialog = copy_form(qtbot, services, event_bus, transfer.outgoing)

    assert dialog.mode_input.index() == TRANSFER_MODE
    assert dialog.account_input.current_id() == pesos.id
    assert dialog.to_account_input.current_id() == dollars.id
    assert dialog.amount_input.money() == ars("120000")


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> TransactionsPage:
    transactions = TransactionsPage(services, event_bus, theme_manager)
    in_view(transactions, event_bus)
    qtbot.addWidget(transactions)
    transactions.refresh()
    return transactions


def test_the_menu_of_a_movement_duplicates_it(monkeypatch, services, cafe, page):
    opened = []
    monkeypatch.setattr(TransactionDialog, "exec", lambda dialog: opened.append(dialog))

    run_action(page.list_view.row_actions(0), "Duplicar")

    assert opened[0].note_input.text() == "Café con medialunas"
    assert opened[0].windowTitle() == "Nueva transacción"


def test_an_installment_is_not_duplicated_but_its_purchase_edited(services, pesos, page):
    draft = expense_draft(services, pesos.id, ars("60000"), TODAY, note="Heladera")
    services.installments.create(draft, InstallmentPlan(None, 6, ars("60000"), TODAY))
    page.refresh()

    assert "Duplicar" not in texts(page.list_view.row_actions(0))


def test_ctrl_k_repeats_the_last_expense(monkeypatch, window, cafe):
    opened = []
    monkeypatch.setattr(TransactionDialog, "exec", lambda dialog: opened.append(dialog))
    palette = window.open_palette()
    QTest.keyClicks(palette.search_input, "repetir")
    assert palette.shown[0].title == "Repetir el último gasto"
    palette.run_chosen()

    assert opened[0].payee_input.text() == "La Esquina"
    assert opened[0].date_input.day() == TODAY


def test_without_expenses_ctrl_k_has_nothing_to_repeat(window):
    palette = window.open_palette()
    QTest.keyClicks(palette.search_input, "repetir")

    assert all(c.title != "Repetir el último gasto" for c in palette.shown)
