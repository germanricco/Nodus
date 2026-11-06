"""Alphabetical ordering and searching of Spanish names."""

import unicodedata
from typing import Protocol, TypeVar

from nodus.models.payee import normalize_name


def name_sort_key(name: str) -> str:
    """Key that orders names ignoring case and accents, so "Árbol" sorts next to "Arroz".

    SQLite's NOCASE collation only folds ASCII and would push accented initials to the end.
    """
    decomposed = unicodedata.normalize("NFD", name.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class Named(Protocol):
    name: str

    @property
    def normalized_name(self) -> str: ...


N = TypeVar("N", bound=Named)


def rank_matches(items: list[N], text: str) -> list[N]:
    """The ``items`` whose name contains ``text``, ignoring case, accents and signs, those
    starting with it first and then alphabetically. Nothing for an empty ``text``."""
    wanted = normalize_name(text)
    if not wanted:
        return []
    found = [item for item in items if wanted in item.normalized_name]
    return sorted(
        found,
        key=lambda item: (not item.normalized_name.startswith(wanted), name_sort_key(item.name)),
    )
