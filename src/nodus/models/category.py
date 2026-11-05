"""Categories that classify income and expenses."""

from __future__ import annotations

from dataclasses import dataclass

from nodus.models.transaction import TransactionType


@dataclass(frozen=True)
class Category:
    """A user-defined label for transactions of one kind (income or expense).

    ``parent_id`` makes it a subcategory, which always has its parent's kind. System
    categories ("Otros", one per kind) receive the transactions of deleted categories,
    so they cannot be edited or deleted.
    """

    id: int | None
    name: str
    kind: TransactionType
    color: str
    parent_id: int | None = None
    is_system: bool = False

    @property
    def is_subcategory(self) -> bool:
        return self.parent_id is not None
