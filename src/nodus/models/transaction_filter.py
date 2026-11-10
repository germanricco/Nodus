"""What to look for when listing transactions, shared by the interface, services and storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nodus.models.transaction import TransactionType


@dataclass(frozen=True)
class TransactionFilter:
    """Criteria for listing transactions. Unset fields do not filter.

    ``category_id`` also matches the category's subcategories, and ``text`` searches the note
    and the names of the payee and the tags, these ignoring case and accents.
    ``is_transfer`` keeps only transfer legs (True) or only income and expenses (False), and
    ``refund_linked`` only refunds and refunded expenses (True) or neither (False).
    ``installment_plan_id`` keeps the installments of one purchase.
    Dates are inclusive.
    """

    start: date | None = None
    end: date | None = None
    account_id: int | None = None
    category_id: int | None = None
    payee_id: int | None = None
    tag_id: int | None = None
    type: TransactionType | None = None
    text: str | None = None
    is_transfer: bool | None = None
    refund_linked: bool | None = None
    installment_plan_id: int | None = None
    limit: int | None = None
