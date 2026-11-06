"""Changes in the value of an investment that are neither income nor expense."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nodus.models.money import Money


@dataclass(frozen=True)
class ValueAdjustment:
    """What an account gained (positive ``amount``) or lost on ``occurred_on`` by itself,
    as interest or a change in prices. It moves the balance and the net worth, never the
    income or the expenses."""

    id: int | None
    account_id: int
    occurred_on: date
    amount: Money
    note: str = ""

    def __post_init__(self) -> None:
        if self.amount.is_zero:
            raise ValueError("A value adjustment changes the balance")
