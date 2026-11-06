import dataclasses
import sqlite3
from datetime import date

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.database.repositories.tag_repository import TagRepository
from nodus.database.repositories.transaction_repository import (
    TransactionFilter,
    TransactionRepository,
)
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.tag import Tag
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


# Refunds and tags


def add_refund(database, services, pesos, expense, amount: str, note: str):
    """An income linked to ``expense``, stored directly: the service links them in v0.9."""
    income = services.transactions.create(
        income_draft(services, pesos.id, ars(amount), date(2026, 11, 6), note=note)
    )
    linked = dataclasses.replace(income, refund_of_id=expense.id)
    TransactionRepository(database).update(linked)
    return linked


@pytest.fixture
def refunded(database, services, pesos, history):
    """The rent ("alquiler") with a refund of $ 100."""
    (rent,) = TransactionRepository(database).list(TransactionFilter(text="alquiler"))
    refund = add_refund(database, services, pesos, rent, "100", "devolución")
    return rent, refund


def test_refund_is_stored_and_listed_by_expense(database, refunded):
    rent, refund = refunded
    repository = TransactionRepository(database)

    assert repository.get(refund.id).refund_of_id == rent.id
    assert [t.note for t in repository.list_refunds_of(rent.id)] == ["devolución"]


def test_refund_linked_filter_keeps_both_sides(database, refunded):
    assert notes(database, refund_linked=True) == ["devolución", "alquiler"]
    assert "alquiler" not in notes(database, refund_linked=False)


def test_deleting_the_expense_frees_its_refunds(database, refunded):
    rent, refund = refunded
    repository = TransactionRepository(database)

    repository.delete(rent.id)

    assert repository.get(refund.id).refund_of_id is None


def test_unlink_refunds(database, refunded):
    rent, refund = refunded
    repository = TransactionRepository(database)

    repository.unlink_refunds_of(rent.id)

    assert repository.get(refund.id).refund_of_id is None


def tag(database, name: str) -> Tag:
    return TagRepository(database).add(Tag(None, name, "#123456"))


def tagged(database, *tags: Tag, text: str) -> int:
    (transaction,) = TransactionRepository(database).list(TransactionFilter(text=text))
    TagRepository(database).set_for(transaction.id, [t.id for t in tags])
    return transaction.id


def test_filter_and_search_by_tag(database, history):
    viaje = tag(database, "Vacaciones 2026")
    tagged(database, viaje, text="kiosco")
    tagged(database, viaje, text="sueldo")

    assert notes(database, tag_id=viaje.id) == ["kiosco", "sueldo"]
    assert notes(database, text="vacaciónes") == ["kiosco", "sueldo"]


def test_tags_for_and_replacing_them(database, history):
    a, b = tag(database, "Bravo"), tag(database, "alfa")
    kiosco = tagged(database, a, b, text="kiosco")
    repository = TagRepository(database)

    assert [t.name for t in repository.tags_for([kiosco])[kiosco]] == ["alfa", "Bravo"]

    repository.set_for(kiosco, [a.id])
    assert repository.tags_for([kiosco, 999]) == {kiosco: [a]}


def test_tag_names_are_unique_once_normalized(database):
    tag(database, "Mudanza")

    with pytest.raises(sqlite3.IntegrityError):
        tag(database, "mudanza")
    assert TagRepository(database).find_by_normalized("mudanza").name == "Mudanza"


def test_reassign_merges_without_duplicates(database, history):
    a, b = tag(database, "Viaje"), tag(database, "Vacaciones")
    both = tagged(database, a, b, text="kiosco")
    only_a = tagged(database, a, text="sueldo")
    repository = TagRepository(database)

    repository.reassign(a.id, b.id)

    assert repository.tags_for([both, only_a]) == {both: [b], only_a: [b]}
    assert repository.count_transactions(a.id) == 0


def test_deleting_a_tag_or_a_transaction_removes_the_links(database, history):
    viaje = tag(database, "Viaje")
    kiosco = tagged(database, viaje, text="kiosco")
    tagged(database, viaje, text="sueldo")
    tags = TagRepository(database)

    TransactionRepository(database).delete(kiosco)
    assert tags.count_transactions(viaje.id) == 1

    tags.delete(viaje.id)
    assert notes(database, text="sueldo") == ["sueldo"]
