"""What a movement asks of its account, for income, expenses and transfers alike."""

from __future__ import annotations

from nodus.database.repositories.account_repository import AccountRepository
from nodus.models.account import Account
from nodus.models.money import Money
from nodus.services.errors import ValidationError, require_found, require_storable


def active_account(accounts: AccountRepository, account_id: int, field: str) -> Account:
    """The account, if it exists and is not archived; ``field`` names it in the draft."""
    account = require_found(accounts.get(account_id), "La cuenta no existe.")
    if account.is_archived:
        raise ValidationError(f"La cuenta «{account.name}» está archivada.", field=field)
    return account


def require_amount_for(amount: Money, account: Account, field: str) -> None:
    """``amount`` is positive and in the account's currency; ``field`` names it."""
    if amount.currency is not account.currency:
        raise ValidationError(
            f"El monto debe estar en {account.currency.value}, la moneda de «{account.name}».",
            field=field,
        )
    if amount.cents <= 0:
        raise ValidationError("El monto debe ser mayor que cero.", field=field)
    require_storable(amount, field)
