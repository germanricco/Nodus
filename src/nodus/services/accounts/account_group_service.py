"""Business rules for account groups: unique names, the user's order, which account is in
which group and what each group adds up to."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.account_group_repository import AccountGroupRepository
from nodus.database.repositories.account_repository import AccountRepository
from nodus.i18n import _
from nodus.models.account import Account
from nodus.models.account_group import AccountGroup
from nodus.models.money import Money
from nodus.services.accounts.account_service import AccountService
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.app.settings_service import SettingsService
from nodus.services.app.undo_service import UndoService, changed_since
from nodus.services.errors import ValidationError, clean_name, require_found, require_free_name
from nodus.services.sorting import name_sort_key


@dataclass(frozen=True)
class GroupTotal:
    """What a group's accounts add up to. With accounts in more than one currency, it is
    converted to the net worth's currency at the day's rate and ``approximate``; without a
    rate for one of them, ``amount`` is None."""

    amount: Money | None
    approximate: bool = False


@dataclass(frozen=True)
class AccountSection:
    """A group with its accounts in the user's order; ``group`` is None for the accounts
    in no group, which come last."""

    group: AccountGroup | None
    accounts: list[Account]


class AccountGroupService:
    """Groups gather accounts (Bancos, Billeteras, Inversiones…) so that a long list stays
    readable, each with its subtotal. One level deep: a group holds accounts, not groups."""

    def __init__(
        self,
        database: Database,
        groups: AccountGroupRepository,
        account_repository: AccountRepository,
        accounts: AccountService,
        exchange_rates: ExchangeRateService,
        settings: SettingsService,
        undo: UndoService,
    ) -> None:
        self._database = database
        self._undo = undo
        self._groups = groups
        self._account_repository = account_repository
        self._accounts = accounts
        self._exchange_rates = exchange_rates
        self._settings = settings

    def list_groups(self) -> list[AccountGroup]:
        """Every group, in the user's order."""
        return sorted(self._groups.list(), key=lambda g: (g.position, name_sort_key(g.name)))

    def get(self, group_id: int) -> AccountGroup:
        return require_found(self._groups.get(group_id), _("El grupo no existe."))

    def create(self, name: str) -> AccountGroup:
        """A new group, last in the order."""
        group = self._checked(AccountGroup(None, clean_name(name)))
        with self._database.transaction():
            position = self._groups.next_position()
            return self._groups.add(dataclasses.replace(group, position=position))

    def rename(self, group_id: int, name: str) -> None:
        group = self._checked(dataclasses.replace(self.get(group_id), name=clean_name(name)))
        with self._database.transaction():
            self._groups.update(group)

    def reorder(self, group_ids: list[int]) -> None:
        """Puts the groups in the order of ``group_ids``, which must name each one once."""
        known = {g.id for g in self._groups.list()}
        if len(group_ids) != len(known) or set(group_ids) != known:
            raise ValidationError(_("La lista de grupos no es válida."))
        with self._database.transaction():
            self._groups.set_positions({group_id: i for i, group_id in enumerate(group_ids)})

    def account_count(self, group_id: int) -> int:
        """How many accounts, archived included, the group holds."""
        return sum(
            1
            for account in self._accounts.list_accounts(include_archived=True)
            if account.group_id == group_id
        )

    def delete(self, group_id: int) -> None:
        """Deletes the group. Its accounts stay, with no group: money and history are never
        part of what a group takes with it."""
        self.get(group_id)
        with self._database.transaction():
            self._groups.delete(group_id)

    def move_account(self, account_id: int, group_id: int | None) -> None:
        """Puts the account in ``group_id`` (or in none), last among its accounts."""
        account = self._accounts.get(account_id)
        if group_id is not None:
            self.get(group_id)
        if account.group_id == group_id:
            return
        with self._database.transaction():
            position = self._account_repository.next_position()
            self._account_repository.update(
                dataclasses.replace(account, group_id=group_id, position=position)
            )

    def place_account(self, account_id: int, group_id: int | None, index: int) -> None:
        """Puts the account in ``group_id`` (or in none) at gap ``index`` among the
        group's active accounts, as when it is dragged there; it can be undone.

        Positions are one order across every account, so the account goes right before
        the one now at ``index`` in the group, or right after the group's last one."""
        account = self._accounts.get(account_id)
        group_name = self.get(group_id).name if group_id is not None else None
        before = self._accounts.list_accounts(include_archived=True)
        order = [a for a in before if a.id != account_id]
        members = [i for i, a in enumerate(order) if a.group_id == group_id and not a.is_archived]
        after_last = members[-1] + 1 if members else len(order)
        at = members[index] if index < len(members) else after_last
        order.insert(at, dataclasses.replace(account, group_id=group_id))
        with self._database.transaction():
            self._account_repository.set_positions({a.id: i for i, a in enumerate(order)})
            self._account_repository.update(
                dataclasses.replace(account, group_id=group_id, position=at)
            )
        where = (
            _("ahora está en {group_name}").format(group_name=group_name)
            if group_name
            else _("quedó sin grupo")
        )
        self._undo.offer(
            f"{account.name} {where}.",
            lambda: self._put_back(before, [a.id for a in order], account_id, group_id),
        )

    def _put_back(
        self, before: list[Account], after: list[int], account_id: int, group_id: int | None
    ) -> None:
        """Undoes ``place_account``: every account where it was, if the order and the
        account's group are still as the drag left them."""
        now = self._accounts.list_accounts(include_archived=True)
        moved = self._accounts.get(account_id)
        if [a.id for a in now] != after or moved.group_id != group_id:
            raise changed_since(_("El orden de «{moved}»").format(moved=moved.name))
        original = next(a for a in before if a.id == account_id)
        self._account_repository.set_positions({a.id: a.position for a in before})
        self._account_repository.update(
            dataclasses.replace(moved, group_id=original.group_id, position=original.position)
        )

    def sections(self, accounts: list[Account]) -> list[AccountSection]:
        """``accounts`` by group: every group in order, even an empty one, then the
        accounts in no group if there are any. Keeps the order of ``accounts``."""
        sections = [
            AccountSection(group, [a for a in accounts if a.group_id == group.id])
            for group in self.list_groups()
        ]
        known = {section.group.id for section in sections}
        loose = [a for a in accounts if a.group_id not in known]
        if loose:
            sections.append(AccountSection(None, loose))
        return sections

    def total(self, accounts: list[Account], balances: dict[int, Money], day: date) -> GroupTotal:
        """What ``accounts`` hold together on ``day``: exact in their currency when they
        share one, converted to the net worth's currency otherwise."""
        currencies = {account.currency for account in accounts}
        if len(currencies) <= 1:
            currency = currencies.pop() if currencies else self._settings.net_worth_currency()
            total = Money.zero(currency)
            for account in accounts:
                total += balances[account.id]
            return GroupTotal(total)
        target = self._settings.net_worth_currency()
        total = Money.zero(target)
        for account in accounts:
            converted = self._exchange_rates.convert(balances[account.id], target, day)
            if converted is None:
                return GroupTotal(None, approximate=True)
            total += converted
        return GroupTotal(total, approximate=True)

    def _checked(self, group: AccountGroup) -> AccountGroup:
        """``group`` if its name is usable and no other group has it."""
        require_free_name(
            group.id,
            group.normalized_name,
            self._groups.find_by_normalized,
            lambda name: _("Ya existe el grupo «{name}».").format(name=name),
        )
        return group
