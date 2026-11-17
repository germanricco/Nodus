"""Payees: who a transaction was paid to or received from."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from nodus.models.names import normalize_name


@dataclass(frozen=True)
class Payee:
    """A shop, company or person. ``default_category_id`` fills in the category of new
    transactions with this payee."""

    id: int | None
    name: str
    default_category_id: int | None = None

    @property
    def normalized_name(self) -> str:
        return normalize_name(self.name)


@dataclass(frozen=True)
class PayeeUsage:
    """How much a payee was used in one kind of transaction over some time: how many
    times, the latest day, and how many times with each category. A purchase in
    installments counts once."""

    uses: int
    last_used: date
    uses_by_category: dict[int, int] = field(default_factory=dict)

    def uses_with(self, category_id: int | None) -> int:
        return self.uses_by_category.get(category_id, 0) if category_id is not None else 0
