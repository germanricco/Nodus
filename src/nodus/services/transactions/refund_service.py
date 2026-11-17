"""How much of each expense has been paid back, and what can still be.

A refund is an income in the Reembolsos category linked to the expense it pays back. Its
cap holds within the expense's currency: refunds in another currency are listed but not
measured against it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.models.money import Money
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.errors import require_found

if TYPE_CHECKING:  # the transaction service builds on this one
    from nodus.services.transactions.transaction_service import TransactionDraft


@dataclass(frozen=True)
class RefundSummary:
    """How much of an expense has been paid back. ``refunded`` adds the refunds in the
    expense's currency; refunds in another currency are listed but have no cap."""

    expense: Transaction
    refunds: list[Transaction]
    refunded: Money

    @property
    def remaining(self) -> Money:
        return self.expense.amount - self.refunded


class RefundService:
    def __init__(self, transactions: TransactionRepository) -> None:
        self._transactions = transactions

    def summary(self, expense_id: int, ignore_id: int | None = None) -> RefundSummary:
        """What has been refunded of ``expense_id``, leaving out ``ignore_id`` (the refund
        being edited, so its own amount does not count against it)."""
        expense = require_found(self._transactions.get(expense_id), "La transacción no existe.")
        refunds = [
            refund
            for refund in self._transactions.list_refunds_of(expense_id)
            if refund.id != ignore_id
        ]
        same_currency = [r.amount for r in refunds if r.amount.currency is expense.amount.currency]
        refunded = sum(same_currency, Money.zero(expense.amount.currency))
        return RefundSummary(expense, refunds, refunded)

    def totals(self) -> dict[int, list[Money]]:
        """What has been refunded of each refunded expense, one amount per currency, read
        at once for lists."""
        return self._transactions.refund_totals()

    def still_refundable(
        self, expenses: list[Transaction], keep_id: int | None = None
    ) -> list[Transaction]:
        """The ``expenses`` whose refunds in their own currency do not cover them yet, in
        their order; ``keep_id``, the one a refund already pays back, stays regardless."""
        refunded = self.totals()

        def covered(expense: Transaction) -> bool:
            same_currency = [
                money.cents
                for money in refunded.get(expense.id, [])
                if money.currency is expense.amount.currency
            ]
            return sum(same_currency) >= expense.amount.cents

        return [e for e in expenses if e.id == keep_id or not covered(e)]

    def excess(self, draft: TransactionDraft, transaction_id: int | None = None) -> Money | None:
        """How much the refund ``draft`` brings back over what is left of its expense, as
        when a friend sends $ 1.000 for a $ 998 share; None when it fits, when it is not a
        refund, or in another currency, which has no cap. ``transaction_id`` is the refund
        being edited, so its own amount does not count as already refunded."""
        if draft.type is not TransactionType.INCOME or draft.refund_of_id is None:
            return None
        remaining = self.summary(draft.refund_of_id, ignore_id=transaction_id).remaining
        if draft.amount.currency is not remaining.currency or not draft.amount > remaining:
            return None
        # Nothing left: the whole amount is no refund at all, and the cap says so.
        if remaining.is_zero or remaining.is_negative:
            return None
        return draft.amount - remaining
