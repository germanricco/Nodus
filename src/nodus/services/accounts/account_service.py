"""Business rules for accounts."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date, datetime

from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.value_adjustment_repository import ValueAdjustmentRepository
from nodus.i18n import _
from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.names import normalize_name
from nodus.models.period import Period
from nodus.models.value_adjustment import ValueAdjustment
from nodus.services.backups.backup_service import BackupService
from nodus.services.errors import (
    ValidationError,
    clean_name,
    require_found,
    require_in_calendar,
    require_storable,
    require_unique_name,
)
from nodus.services.sorting import name_sort_key


@dataclass(frozen=True)
class ValueGain:
    """What a savings or investment account gained (or lost) by itself, and that as a
    share of what was put in; ``share`` is None with nothing put in or nothing gained."""

    amount: Money
    share: float | None


class AccountService:
    """Accounts and their balances: unique names, archiving, the user's order and the
    adjustments of value of investments."""

    def __init__(
        self,
        database: Database,
        accounts: AccountRepository,
        adjustments: ValueAdjustmentRepository,
        backups: BackupService,
    ) -> None:
        self._database = database
        self._accounts = accounts
        self._adjustments = adjustments
        self._backups = backups

    def create(
        self, name: str, account_type: AccountType, currency: Currency, initial_balance: Money
    ) -> Account:
        """Adds the account last in the user's order; its name must be free."""
        require_storable(initial_balance, "initial_balance")
        account = Account(None, clean_name(name), account_type, currency, initial_balance)
        self._require_new_name(account)
        with self._database.transaction():
            position = self._accounts.next_position()
            return self._accounts.add(dataclasses.replace(account, position=position))

    def update(
        self, account_id: int, name: str, account_type: AccountType, initial_balance: Money
    ) -> None:
        """Edits an account. The currency is fixed at creation: changing it would silently
        reinterpret every amount already recorded in the account."""
        existing = self.get(account_id)
        require_storable(initial_balance, "initial_balance")
        if initial_balance.currency is not existing.currency:
            raise ValidationError(_("No se puede cambiar la moneda de una cuenta."))
        updated = dataclasses.replace(
            existing, name=clean_name(name), type=account_type, initial_balance=initial_balance
        )
        # Two accounts that were already called the same can still be edited.
        if normalize_name(updated.name) != normalize_name(existing.name):
            self._require_new_name(updated)
        with self._database.transaction():
            self._accounts.update(updated)

    def set_archived(self, account_id: int, archived: bool) -> None:
        """Archived accounts keep their history but are hidden and accept no new transactions."""
        updated = dataclasses.replace(self.get(account_id), is_archived=archived)
        with self._database.transaction():
            self._accounts.update(updated)

    def transaction_count(self, account_id: int) -> tuple[int, int]:
        """(movements, transfers) that deleting the account would take with it."""
        return self._accounts.count_transactions(self.get(account_id).id)

    def delete(self, account_id: int) -> None:
        """Deletes the account and its movements. Transfers are deleted whole, so the
        other account's balance changes too; archiving is the way to keep the history.
        The data is copied first, and the copy kept for a month."""
        account = self.get(account_id)
        self._backups.create_before_delete(datetime.now())
        with self._database.transaction():
            self._accounts.delete(account.id)

    def get(self, account_id: int) -> Account:
        return require_found(self._accounts.get(account_id), _("La cuenta no existe."))

    def _require_new_name(self, account: Account) -> None:
        """No other account, archived or not, has the same name (case and accents aside),
        so a list or a menu never shows two accounts nobody can tell apart."""
        others = (a.name for a in self._accounts.list(include_archived=True) if a.id != account.id)
        require_unique_name(
            account.name, others, _("Ya hay una cuenta «{account}».").format(account=account.name)
        )

    def list_accounts(self, include_archived: bool = False) -> list[Account]:
        """Accounts in the order the user gave them; alphabetical among equal positions,
        as every account is until the user first moves one."""
        return sorted(
            self._accounts.list(include_archived),
            key=lambda a: (a.position, name_sort_key(a.name)),
        )

    def first_created_on(self) -> date | None:
        """The day the first account was created, or None if there is none."""
        return self._accounts.first_created_on()

    def data_since(self) -> dict[int, date]:
        """The first day each account has data for: its creation or its first movement."""
        return self._accounts.data_since()

    def reorder(self, account_ids: list[int]) -> None:
        """Puts the accounts of ``account_ids`` first, in that order; the rest (the
        archived ones, when the active list is reordered) keep their order after them."""
        known = {a.id for a in self._accounts.list(include_archived=True)}
        if len(set(account_ids)) != len(account_ids) or not set(account_ids) <= known:
            raise ValidationError(_("La lista de cuentas no es válida."))
        rest = [a.id for a in self.list_accounts(include_archived=True) if a.id not in account_ids]
        order = [*account_ids, *rest]
        with self._database.transaction():
            self._accounts.set_positions({account_id: i for i, account_id in enumerate(order)})

    def balances(self, on: date | None = None) -> dict[int, Money]:
        """Balance of every account (archived included) at the end of ``on``, today if None,
        keyed by account id.

        Movements dated later, such as the installments still to come, do not count yet:
        each one comes off the balance on its own day, as it does in the bank.
        """
        currencies = {a.id: a.currency for a in self._accounts.list(include_archived=True)}
        return {
            account_id: Money(cents, currencies[account_id])
            for account_id, cents in self._accounts.balances_cents(on or date.today()).items()
        }

    def balance(self, account_id: int, on: date | None = None) -> Money:
        """The account's balance at the end of ``on``, today if None (see ``balances``)."""
        account = self.get(account_id)
        return self.balances(on)[account.id]

    def adjust_value(
        self, account_id: int, value: Money, day: date, note: str = ""
    ) -> ValueAdjustment | None:
        """Brings the balance at the end of ``day`` to ``value``, what the investment is
        worth, by recording the difference as an adjustment; None when there is none.

        Only savings and investment accounts change value by themselves.
        """
        account = self.get(account_id)
        if not account.type.changes_value:
            raise ValidationError(_("Solo las cuentas de ahorro o inversión cambian de valor."))
        if account.is_archived:
            raise ValidationError(_("La cuenta está archivada."))
        if value.currency is not account.currency:
            raise ValidationError(
                _("El valor va en la moneda de la cuenta ({currency_value}).").format(
                    currency_value=account.currency.value
                ),
                field="value",
            )
        require_storable(value, "value")
        require_in_calendar(day, "day")
        difference = value - self.balance(account.id, day)
        if difference.is_zero:
            return None
        with self._database.transaction():
            return self._adjustments.add(
                ValueAdjustment(None, account.id, day, difference, note.strip())
            )

    def value_adjustments(
        self, account_id: int | None = None, period: Period | None = None
    ) -> list[ValueAdjustment]:
        """Adjustments, oldest first, of one account or all, within ``period`` if given."""
        start, end = (period.start, period.end) if period else (None, None)
        return self._adjustments.list(account_id, start, end)

    def value_change(self, account_id: int) -> Money:
        """What the account gained (or lost) by itself, adding all its adjustments."""
        total = Money.zero(self.get(account_id).currency)
        for adjustment in self._adjustments.list(account_id):
            total += adjustment.amount
        return total

    def value_gain(self, account: Account, balance: Money) -> ValueGain | None:
        """What ``account`` gained by itself, now that it holds ``balance``; None for an
        account whose value does not change by itself."""
        if not account.type.changes_value:
            return None
        gain = self.value_change(account.id)
        invested = balance - gain
        share = gain.cents / invested.cents if invested.cents > 0 and not gain.is_zero else None
        return ValueGain(gain, share)

    def delete_adjustment(self, adjustment_id: int) -> None:
        require_found(self._adjustments.get(adjustment_id), _("El ajuste no existe."))
        with self._database.transaction():
            self._adjustments.delete(adjustment_id)
