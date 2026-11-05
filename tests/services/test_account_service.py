import pytest
from factories import ars, expense_draft, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.errors import NotFoundError, ValidationError


def test_create_trims_name_and_assigns_id(services):
    account = services.accounts.create("  Efectivo ", AccountType.CASH, Currency.ARS, ars("0"))

    assert account.id is not None
    assert services.accounts.get(account.id).name == "Efectivo"


def test_create_rejects_blank_name(services):
    with pytest.raises(ValidationError):
        services.accounts.create("   ", AccountType.CASH, Currency.ARS, ars("0"))


def test_balance_is_initial_plus_income_minus_expenses(services, pesos):
    services.transactions.create(income_draft(services, pesos.id, ars("50000")))
    services.transactions.create(expense_draft(services, pesos.id, ars("12345.67")))

    assert services.accounts.balance(pesos.id) == ars("137654.33")


def test_balances_covers_every_account_in_its_currency(services, pesos, dollars):
    assert services.accounts.balances() == {pesos.id: ars("100000"), dollars.id: usd("500")}


def test_update_changes_name_type_and_initial_balance(services, pesos):
    services.accounts.update(pesos.id, "Banco Nación", AccountType.SAVINGS, ars("90000"))

    updated = services.accounts.get(pesos.id)
    assert (updated.name, updated.type, updated.initial_balance) == (
        "Banco Nación", AccountType.SAVINGS, ars("90000"),
    )  # fmt: skip


def test_update_cannot_change_currency(services, pesos):
    with pytest.raises(ValidationError):
        services.accounts.update(pesos.id, "Banco", AccountType.BANK, usd("1"))


def test_archived_accounts_are_hidden_but_kept(services, pesos, dollars):
    services.accounts.set_archived(dollars.id, True)

    assert [a.id for a in services.accounts.list_accounts()] == [pesos.id]
    assert len(services.accounts.list_accounts(include_archived=True)) == 2

    services.accounts.set_archived(dollars.id, False)
    assert len(services.accounts.list_accounts()) == 2


def test_get_missing_account_raises(services):
    with pytest.raises(NotFoundError):
        services.accounts.get(999)
