from datetime import date, timedelta

import pytest
from factories import TODAY, ars, expense_draft, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.errors import NotFoundError, ValidationError
from nodus.services.transaction_service import TransferDraft


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


def test_a_future_movement_comes_off_the_balance_on_its_own_day(services, pesos):
    """As in the bank: an installment still to come does not lower today's balance."""
    today = date.today()
    tomorrow = today + timedelta(days=1)
    services.transactions.create(expense_draft(services, pesos.id, ars("1000"), tomorrow))

    assert services.accounts.balance(pesos.id) == ars("100000")
    assert services.accounts.balances()[pesos.id] == ars("100000")
    assert services.accounts.balance(pesos.id, tomorrow) == ars("99000")
    assert services.net_worth.net_worth(today).by_currency[Currency.ARS] == ars("100000")


def test_a_movement_dated_today_already_counts(services, pesos):
    services.transactions.create(expense_draft(services, pesos.id, ars("1000"), date.today()))

    assert services.accounts.balance(pesos.id) == ars("99000")


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


def test_delete_takes_movements_and_whole_transfers(services, pesos, dollars):
    services.transactions.create(expense_draft(services, dollars.id, usd("20")))
    services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("120000"), TODAY, amount_in=usd("100"))
    )
    assert services.accounts.transaction_count(dollars.id) == (2, 1)

    services.accounts.delete(dollars.id)

    assert [a.id for a in services.accounts.list_accounts(include_archived=True)] == [pesos.id]
    # The peso leg of the transfer is gone too, so the balance is back to the initial one.
    assert services.accounts.balance(pesos.id) == ars("100000")


def test_delete_unknown_account_raises(services):
    with pytest.raises(NotFoundError):
        services.accounts.delete(999)


class TestOrder:
    def names(self, services, include_archived=False) -> list[str]:
        return [a.name for a in services.accounts.list_accounts(include_archived)]

    def test_new_accounts_go_last(self, services, pesos, dollars):
        services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))

        assert self.names(services) == ["Banco", "Ahorro", "Efectivo"]

    def test_equal_positions_go_by_name(self, services, database):
        """Upgraded databases start with every account at position 0: alphabetical."""
        for name in ("Banco", "Ámbar", "efectivo"):
            services.accounts.create(name, AccountType.CASH, Currency.ARS, ars("0"))
        with database.transaction():
            database.connection.execute("UPDATE accounts SET position = 0")

        assert self.names(services) == ["Ámbar", "Banco", "efectivo"]

    def test_reorder_keeps_archived_accounts_after(self, services, pesos, dollars):
        wallet = services.accounts.create(
            "Mercado Pago", AccountType.WALLET, Currency.ARS, ars("0")
        )
        services.accounts.set_archived(pesos.id, True)

        services.accounts.reorder([wallet.id, dollars.id])

        assert self.names(services) == ["Mercado Pago", "Ahorro"]
        assert self.names(services, include_archived=True) == ["Mercado Pago", "Ahorro", "Banco"]

    @pytest.mark.parametrize("ids", [[1, 1], [1, 99]])
    def test_reorder_rejects_repeated_or_unknown_ids(self, services, pesos, dollars, ids):
        with pytest.raises(ValidationError):
            services.accounts.reorder(ids)
