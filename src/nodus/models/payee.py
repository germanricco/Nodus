"""Payees: who a transaction was paid to or received from."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

_NOT_ALPHANUMERIC = re.compile(r"[^0-9a-z]+")


def normalize_name(name: str) -> str:
    """The form two names must share to be the same payee.

    Lowercase, without accents, with any sign turned into a space and spaces collapsed, so
    "Café  Martínez" and "cafe-martinez" match.
    """
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _NOT_ALPHANUMERIC.sub(" ", plain).strip()


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
