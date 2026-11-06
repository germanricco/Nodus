"""Payees: who a transaction was paid to or received from."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

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
