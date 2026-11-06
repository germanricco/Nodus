"""Accounts where money is held."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from nodus.models.currency import Currency
from nodus.models.money import Money


class AccountType(Enum):
    """Kind of account. The value is what the database stores."""

    CASH = "cash"
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    SAVINGS = "savings"
    INVESTMENT = "investment"

    @property
    def changes_value(self) -> bool:
        """Savings and investments earn interest or follow prices, so their value moves by
        itself and is brought up to date with value adjustments."""
        return self in {AccountType.SAVINGS, AccountType.INVESTMENT}


@dataclass(frozen=True)
class Account:
    """A place holding money in a single currency.

    The current balance is not stored here: it is always computed from the initial balance
    plus the account's transactions, so it can never drift out of sync.
    """

    id: int | None
    name: str
    type: AccountType
    currency: Currency
    initial_balance: Money
    is_archived: bool = False

    def __post_init__(self) -> None:
        if self.initial_balance.currency is not self.currency:
            raise ValueError("Initial balance must be in the account's currency")
