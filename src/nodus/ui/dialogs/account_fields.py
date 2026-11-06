"""Account choices shared by the dialogs that record or plan movements."""

from __future__ import annotations

from collections.abc import Iterable

from nodus.models.account import Account
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.ui.widgets.selectors import AccountComboBox


def selectable_accounts(services: Services, used_ids: Iterable[int] = ()) -> list[Account]:
    """Active accounts, plus the archived ones the edited item already uses, so editing
    it doesn't silently move it to another account."""
    accounts = services.accounts.list_accounts()
    active_ids = {account.id for account in accounts}
    missing = sorted(set(used_ids) - active_ids)
    return accounts + [services.accounts.get(account_id) for account_id in missing]


def required_account(combo: AccountComboBox) -> Account:
    account = combo.current_account()
    if account is None:
        raise ValidationError("Elige una cuenta.")
    return account
