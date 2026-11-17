"""What a user can type or pick, pushed through the services the way the interface does.

Each case is something a person could really do: paste odd text into a name, search for
"%", type far too many digits, pick a file that is not a copy. The services must answer with
a message (``ValidationError``) or store the text exactly, never fail with another error.
Known defects are ``xfail(strict=True)`` with their id in the v1.9 quality audit, so fixing
one forces removing its mark.
"""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from datetime import date, datetime

import pytest
from factories import TODAY, ars, charge_draft, clp, eur, expense_draft, usd

from nodus.database.database import Database
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.goal import GoalShare
from nodus.models.money import Money
from nodus.models.period import FIRST_DAY, LAST_DAY, Month
from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.errors import ValidationError
from nodus.services.planning.goal_service import GoalDraft

# Text a person can paste into any name or note field.
STORED_AS_TYPED = [
    "'; DROP TABLE transactions; --",
    "Robert'); DELETE FROM accounts; --",
    '"entre comillas"',
    "100%",
    "a_b",
    "barra\\invertida",
    "emoji 💸🏦",
    "RTL ‏שלום",
    "ancho​cero",
    "x" * 10_000,
    "Ñandú",
]
BLANK = ["", "   ", "\n", "\t"]
ABSURD_CENTS = 10**20  # far beyond any balance; more than SQLite's INTEGER holds


def create_named(services, kind: str, name: str) -> str:
    """Creates a ``kind`` named ``name`` as its dialog does and returns the stored name."""
    if kind == "account":
        created = services.accounts.create(name, AccountType.CASH, Currency.ARS, ars("0"))
    elif kind == "category":
        created = services.categories.create(name, TransactionType.EXPENSE, "#123456")
    elif kind == "payee":
        created = services.payees.create(name)
    elif kind == "tag":
        created = services.tags.create(name)
    else:
        created = services.account_groups.create(name)
    return created.name


KINDS = ["account", "category", "payee", "tag", "group"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("name", STORED_AS_TYPED, ids=lambda n: repr(n[:20]))
def test_odd_names_are_stored_exactly(services, kind, name):
    assert create_named(services, kind, name) == name


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("name", BLANK, ids=repr)
def test_blank_names_are_refused_with_a_message(services, kind, name):
    with pytest.raises(ValidationError):
        create_named(services, kind, name)


@pytest.mark.parametrize("kind", ["payee", "tag", "group"])
def test_names_without_letters_are_refused_with_a_message(services, kind):
    with pytest.raises(ValidationError):
        create_named(services, kind, "!!!")


def test_sql_in_every_text_field_leaves_the_data_intact(services, pesos):
    attack = "x'); DROP TABLE transactions; --"
    services.transactions.create(
        expense_draft(
            services, pesos.id, ars("10"), note=attack, payee_name=attack, tag_names=(attack,)
        )
    )
    services.transactions.list_transactions(TransactionFilter(text=attack))
    (saved,) = services.transactions.list_transactions(TransactionFilter())
    assert saved.note == attack
    assert services.payees.list_payees()[0].name == attack
    assert services.accounts.get(pesos.id).name == "Banco"


@pytest.mark.parametrize("text", ["'", '"', "\\", "[", "*", "💸", "x" * 5000], ids=repr)
def test_any_search_text_returns_a_list(services, pesos, text):
    services.transactions.create(expense_draft(services, pesos.id, ars("10"), note="algo"))
    assert services.transactions.list_transactions(TransactionFilter(text=text)) == []


@pytest.mark.parametrize("text,expected", [("%", ["descuento 50%"]), ("_", ["a_b"])])
def test_search_treats_percent_and_underscore_as_text(services, pesos, text, expected):
    for note in ["descuento 50%", "pago 500", "a_b", "axb"]:
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), note=note))
    found = services.transactions.list_transactions(TransactionFilter(text=text))
    assert [t.note for t in found] == expected


@pytest.mark.parametrize("cents", [0, -100])
def test_amounts_that_are_not_positive_are_refused(services, pesos, cents):
    with pytest.raises(ValidationError):
        services.transactions.create(expense_draft(services, pesos.id, Money(cents, Currency.ARS)))


@pytest.mark.parametrize("save", ["expense", "budget", "initial balance"])
def test_absurd_amounts_are_refused_with_a_message(services, pesos, save):
    absurd = Money(ABSURD_CENTS, Currency.ARS)
    category = services.categories.list_categories(TransactionType.EXPENSE)[0].id
    with pytest.raises(ValidationError):
        if save == "expense":
            services.transactions.create(expense_draft(services, pesos.id, absurd))
        elif save == "budget":
            services.budgets.set_limit(category, Month.of(TODAY), absurd)
        else:
            services.accounts.create("Enorme", AccountType.CASH, Currency.ARS, absurd)


@pytest.mark.parametrize("save", ["expense", "charge", "initial balance", "value"])
def test_chilean_pesos_with_cents_are_refused_by_the_services(services, save):
    """The field refuses them first; the services do too, so no other way of saving an
    amount (Telegram, a script) stores cents that no screen shows."""
    with_cents = Money(12_350, Currency.CLP)
    savings = services.accounts.create("Chile", AccountType.SAVINGS, Currency.CLP, clp("0"))
    with pytest.raises(ValidationError, match="Los pesos chilenos no llevan centavos."):
        if save == "expense":
            services.transactions.create(expense_draft(services, savings.id, with_cents))
        elif save == "charge":
            services.recurring.create(charge_draft(services, savings.id, with_cents))
        elif save == "initial balance":
            services.accounts.create("Otra", AccountType.CASH, Currency.CLP, with_cents)
        else:
            services.accounts.adjust_value(savings.id, with_cents, TODAY)


def test_the_largest_amounts_accepted_still_add_up(services, pesos):
    largest = Money(2**63 - 1, Currency.ARS)
    for _ in range(2):
        with suppress(ValidationError):  # refusing them is fine; a broken balance is not
            services.transactions.create(expense_draft(services, pesos.id, largest))
    services.accounts.balances()


def test_recurring_summary_with_a_charge_that_cannot_be_converted(services, euros):
    services.recurring.create(charge_draft(services, euros.id, eur("9.99")))
    summary = services.recurring.summary(TODAY)
    assert summary.monthly == ars("0")


@pytest.mark.parametrize("frequency", list(Frequency))
@pytest.mark.parametrize("due", [FIRST_DAY, date(2100, 1, 31)])
def test_skipping_a_charge_at_reasonable_date_edges(services, pesos, frequency, due):
    charge = services.recurring.create(
        charge_draft(services, pesos.id, ars("100"), due=due, frequency=frequency)
    )
    services.recurring.skip(charge.id)
    assert services.recurring.get(charge.id).next_due_on > due


@pytest.mark.parametrize("frequency", [Frequency.WEEKLY, Frequency.MONTHLY, Frequency.ANNUAL])
def test_skipping_a_charge_due_at_the_calendars_last_day(services, pesos, frequency):
    charge = services.recurring.create(
        charge_draft(services, pesos.id, ars("100"), due=LAST_DAY, frequency=frequency)
    )
    services.recurring.skip(charge.id)
    assert services.recurring.get(charge.id).next_due_on > LAST_DAY


@pytest.mark.parametrize("day", [date(9999, 12, 31), date(1, 1, 1)], ids=["9999", "year 1"])
def test_dates_outside_the_calendar_are_refused_with_a_message(services, pesos, day):
    with pytest.raises(ValidationError):
        services.recurring.create(charge_draft(services, pesos.id, ars("100"), due=day))
    with pytest.raises(ValidationError):
        services.transactions.create(expense_draft(services, pesos.id, ars("10"), on=day))


def write(folder, name: str, content: bytes):
    path = folder / name
    path.write_bytes(content)
    return path


@pytest.mark.parametrize(
    "content",
    [b"", b"hola", b"\x89PNG\r\n\x1a\n" + b"\x00" * 200, b"SQLite format 3\x00" + b"\xff" * 100],
    ids=["empty", "text", "image", "broken header"],
)
def test_restoring_a_file_that_is_not_a_copy_gives_a_message(services, pesos, tmp_path, content):
    source = write(tmp_path, "copia.db", content)
    with pytest.raises(ValidationError):
        services.backups.restore(source, datetime(2026, 11, 5, 10))
    assert services.accounts.get(pesos.id).name == "Banco"


def test_restoring_another_apps_database_gives_a_message(services, tmp_path):
    other = tmp_path / "otra.db"
    with sqlite3.connect(other) as connection:
        connection.execute("CREATE TABLE notes (text TEXT)")
    with pytest.raises(ValidationError):
        services.backups.restore(other, datetime(2026, 11, 5, 10))


@pytest.mark.parametrize(
    "folder_name",
    [
        "con espacio",
        "ñandú",
        "100%",
        "[corchetes]",
        "a&b",
        "copia #1",
    ],
)
def test_a_copy_outside_the_pc_can_be_restored_from_any_folder_name(
    services, pesos, tmp_path, folder_name
):
    folder = tmp_path / folder_name
    folder.mkdir()
    copy = services.backups.export_to(folder, TODAY)
    services.accounts.update(pesos.id, "Cambiado", pesos.type, pesos.initial_balance)
    services.backups.restore(copy, datetime(2026, 11, 5, 10))
    assert services.accounts.get(pesos.id).name == "Banco"


def test_restoring_leaves_only_the_copy_on_the_pen_drive(services, tmp_path):
    """A copy is opened read-only, so the pen drive keeps exactly the file the user saved
    (and a write-protected one can be read at all)."""
    folder = tmp_path / "pendrive"
    folder.mkdir()
    copy = services.backups.export_to(folder, TODAY)
    services.backups.restore(copy, datetime(2026, 11, 5, 10))
    assert [p.name for p in folder.iterdir()] == [copy.name]


def test_inspecting_a_copy_in_a_folder_with_a_hash_reads_that_copy(tmp_path):
    folder = tmp_path / "copia #1"
    folder.mkdir()
    Database.open(folder / "nodus.db").close()
    assert Database.inspect(folder / "nodus.db") > 0


# Actions in an order the interface allows but nobody planned for. Each must give a message
# or leave the data consistent.


def test_undo_with_nothing_to_undo_gives_a_message(services):
    with pytest.raises(ValidationError):
        services.undo.undo()


@pytest.mark.parametrize("kind", ["payee", "tag"])
def test_merging_into_itself_gives_a_message(services, kind):
    service = services.payees if kind == "payee" else services.tags
    item = service.create("Uno")
    with pytest.raises(ValidationError):
        service.merge_many([item.id], item.id)


def test_merging_into_one_just_deleted_gives_a_message(services):
    kept, gone = services.payees.create("Coto"), services.payees.create("Dia")
    services.payees.delete_many([gone.id])
    with pytest.raises(ValidationError):
        services.payees.merge_many([kept.id], gone.id)


def test_deleting_a_transaction_already_gone_gives_a_message(services):
    with pytest.raises(ValidationError):
        services.transactions.delete_many([999])


def test_deleting_a_refunded_expense_keeps_the_refund_as_an_income(services, pesos):
    expense = services.transactions.create(expense_draft(services, pesos.id, ars("100")))
    refund = services.transactions.create(
        expense_draft(
            services,
            pesos.id,
            ars("40"),
            type=TransactionType.INCOME,
            category_id=refunds_category(services),
            refund_of_id=expense.id,
        )
    )
    services.transactions.delete_many([expense.id])
    assert services.transactions.get(refund.id).refund_of_id is None


def test_an_archived_accounts_charge_cannot_be_paid_into_it(services, pesos):
    charge = services.recurring.create(charge_draft(services, pesos.id, ars("100")))
    services.accounts.set_archived(pesos.id, True)
    with pytest.raises(ValidationError):
        services.recurring.pay(charge.id, ars("100"), TODAY, pesos.id)
    assert services.recurring.summary(TODAY).active == 1


def test_deleting_the_category_of_a_charge_and_a_budget(services, pesos):
    charge = services.recurring.create(charge_draft(services, pesos.id, ars("100")))
    services.budgets.set_limit(charge.category_id, Month.of(TODAY), ars("500"))
    services.categories.delete(charge.category_id)
    assert services.recurring.get(charge.id).category_id != charge.category_id
    services.budgets.month_budgets(Month.of(TODAY), TODAY)


def test_deleting_the_account_a_goal_uses_keeps_the_goal(services, dollars):
    goal = services.goals.create(
        GoalDraft("Auto", usd("1000"), None, (GoalShare(dollars.id, 60),)), TODAY
    )
    services.accounts.delete(dollars.id)
    services.goals.progress(services.goals.get(goal.id), TODAY)


def refunds_category(services) -> int:
    return next(
        c.id
        for c in services.categories.list_categories(TransactionType.INCOME)
        if c.name == "Reembolsos"
    )
