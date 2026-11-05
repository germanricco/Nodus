"""Alphabetical ordering for Spanish names."""

import unicodedata


def name_sort_key(name: str) -> str:
    """Key that orders names ignoring case and accents, so "Árbol" sorts next to "Arroz".

    SQLite's NOCASE collation only folds ASCII and would push accented initials to the end.
    """
    decomposed = unicodedata.normalize("NFD", name.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))
