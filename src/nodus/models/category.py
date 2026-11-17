"""Categories that classify income and expenses."""

from __future__ import annotations

from dataclasses import dataclass

from nodus.models.transaction import TransactionType


@dataclass(frozen=True)
class Category:
    """A user-defined label for transactions of one kind (income or expense).

    ``parent_id`` makes it a subcategory, which always has its parent's kind. System
    categories ("Otros", one per kind) receive the transactions of deleted categories,
    and ``is_refunds`` marks the income category whose movements can be linked to an
    expense as its refund; neither can be edited or deleted (``is_fixed``).
    """

    id: int | None
    name: str
    kind: TransactionType
    color: str
    parent_id: int | None = None
    is_system: bool = False
    is_refunds: bool = False

    @property
    def is_fixed(self) -> bool:
        """Nodus relies on it, so it cannot be renamed, deleted or given subcategories."""
        return self.is_system or self.is_refunds

    @property
    def is_subcategory(self) -> bool:
        return self.parent_id is not None
