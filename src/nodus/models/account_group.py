"""Groups of accounts: Bancos, Billeteras, Inversiones…"""

from __future__ import annotations

from dataclasses import dataclass

from nodus.models.payee import normalize_name


@dataclass(frozen=True)
class AccountGroup:
    """A named set of accounts, shown together with their subtotal. Its name is unique
    once normalized, as a tag's, and ``position`` is its place in the user's order."""

    id: int | None
    name: str
    position: int = 0

    @property
    def normalized_name(self) -> str:
        return normalize_name(self.name)
