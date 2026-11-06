"""Money movements: income, expenses and transfers between accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.models.money import Money


class TransactionType(Enum):
    """Direction of a transaction. Categories reuse it to say which transactions they apply to."""

    INCOME = "income"
    EXPENSE = "expense"


INCOME = TransactionType.INCOME


@dataclass(frozen=True)
class Transaction:
    """One movement in one account.

    ``amount`` is always positive; ``type`` gives the direction. Its currency is the
    account's currency. A transaction with a ``transfer_id`` is one leg of a transfer and
    has no category or payee; every other transaction has a category and may have a payee.
    An income with ``refund_of_id`` pays back that expense, so totals count it as less
    spending instead of as income.
    """

    id: int | None
    account_id: int
    type: TransactionType
    amount: Money
    occurred_on: date
    category_id: int | None
    note: str = ""
    transfer_id: str | None = None
    payee_id: int | None = None
    refund_of_id: int | None = None

    def __post_init__(self) -> None:
        if self.amount.cents <= 0:
            raise ValueError("Transaction amount must be positive")
        if self.is_transfer == (self.category_id is not None):
            raise ValueError("A transaction has either a category or a transfer_id, not both")
        if self.is_transfer and self.payee_id is not None:
            raise ValueError("A transfer has no payee")
        if self.refund_of_id is not None and (self.is_transfer or self.type is not INCOME):
            raise ValueError("Only an income that is not a transfer can be a refund")

    @property
    def is_transfer(self) -> bool:
        return self.transfer_id is not None

    @property
    def signed_amount(self) -> Money:
        """Amount with its effect on the account balance: negative for expenses."""
        return self.amount if self.type is TransactionType.INCOME else -self.amount


@dataclass(frozen=True)
class Transfer:
    """A movement between two of the user's accounts, stored as two linked transactions."""

    outgoing: Transaction
    incoming: Transaction

    @property
    def id(self) -> str:
        return self.outgoing.transfer_id
