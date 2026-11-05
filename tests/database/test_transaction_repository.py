from datetime import date

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.database.repositories.transaction_repository import (
    TransactionFilter,
    TransactionRepository,
)
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.transaction import TransactionType
from nodus.services.transaction_service import TransferDraft

EXPENSE = TransactionType.EXPENSE


@pytest.fixture
def history(services, pesos):
    """Five transactions across two accounts and two months, identified by their note."""
    efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))
    vivienda = category_id(services, "Vivienda", EXPENSE)
    alquiler = services.categories.create("Alquiler", EXPENSE, "#000000", parent_id=vivienda)
    for draft in [
        expense_draft(services, pesos.id, ars("10"), date(2026, 10, 3), note="super octubre"),
        income_draft(services, pesos.id, ars("500"), date(2026, 11, 1), note="sueldo"),
        expense_draft(
            services, pesos.id, ars("300"), date(2026, 11, 2),
            category_id=alquiler.id, note="alquiler",
        ),
        expense_draft(
            services, pesos.id, ars("50"), date(2026, 11, 3), category_id=vivienda, note="expensas"
        ),
        expense_draft(services, efectivo.id, ars("5"), date(2026, 11, 4), note="kiosco"),
    ]:  # fmt: skip
        services.transactions.create(draft)
    return efectivo, vivienda


def notes(database, **criteria):
    found = TransactionRepository(database).list(TransactionFilter(**criteria))
    return [t.note for t in found]


def test_no_filter_returns_all_newest_first(database, history):
    assert notes(database) == ["kiosco", "expensas", "alquiler", "sueldo", "super octubre"]


def test_date_range_is_inclusive(database, history):
    assert notes(database, start=date(2026, 11, 2), end=date(2026, 11, 3)) == [
        "expensas", "alquiler",
    ]  # fmt: skip


def test_by_account(database, history):
    efectivo, _ = history
    assert notes(database, account_id=efectivo.id) == ["kiosco"]


def test_by_category_includes_subcategories(database, history):
    _, vivienda = history
    assert notes(database, category_id=vivienda) == ["expensas", "alquiler"]


def test_by_type(database, history):
    assert notes(database, type=TransactionType.INCOME) == ["sueldo"]


def test_by_text_in_note(database, history):
    assert notes(database, text="octu") == ["super octubre"]


def test_limit(database, history):
    assert notes(database, limit=2) == ["kiosco", "expensas"]


def test_by_transfer_flag(database, services, pesos, dollars, history):
    services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("1200"), date(2026, 11, 5), amount_in=usd("1"),
                      note="dólares")
    )  # fmt: skip

    assert notes(database, is_transfer=True) == ["dólares", "dólares"]
    assert "dólares" not in notes(database, is_transfer=False)
    assert len(notes(database, is_transfer=False)) == 5
