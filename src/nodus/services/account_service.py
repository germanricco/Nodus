"""Business rules for accounts."""

from __future__ import annotations

import dataclasses

from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.services.errors import ValidationError, clean_name, require_found


class AccountService:
    def __init__(self, database: Database, accounts: AccountRepository) -> None:
        self._database = database
        self._accounts = accounts

    def create(
        self, name: str, account_type: AccountType, currency: Currency, initial_balance: Money
    ) -> Account:
        account = Account(None, clean_name(name), account_type, currency, initial_balance)
        with self._database.transaction():
            return self._accounts.add(account)

    def update(
        self, account_id: int, name: str, account_type: AccountType, initial_balance: Money
    ) -> None:
        """Edits an account. The currency is fixed at creation: changing it would silently
        reinterpret every amount already recorded in the account."""
        existing = self.get(account_id)
        if initial_balance.currency is not existing.currency:
            raise ValidationError("No se puede cambiar la moneda de una cuenta.")
        updated = dataclasses.replace(
            existing, name=clean_name(name), type=account_type, initial_balance=initial_balance
        )
        with self._database.transaction():
            self._accounts.update(updated)

    def set_archived(self, account_id: int, archived: bool) -> None:
        """Archived accounts keep their history but are hidden and accept no new transactions."""
        updated = dataclasses.replace(self.get(account_id), is_archived=archived)
        with self._database.transaction():
            self._accounts.update(updated)

    def get(self, account_id: int) -> Account:
        return require_found(self._accounts.get(account_id), "La cuenta no existe.")

    def list_accounts(self, include_archived: bool = False) -> list[Account]:
        return self._accounts.list(include_archived)

    def balances(self) -> dict[int, Money]:
        """Current balance of every account (archived included), keyed by account id."""
        currencies = {a.id: a.currency for a in self._accounts.list(include_archived=True)}
        return {
            account_id: Money(cents, currencies[account_id])
            for account_id, cents in self._accounts.balances_cents().items()
        }

    def balance(self, account_id: int) -> Money:
        account = self.get(account_id)
        return Money(self._accounts.balances_cents()[account.id], account.currency)
