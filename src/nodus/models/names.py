"""How names compare: the one rule for payees, tags, accounts, categories and groups."""

import re
import unicodedata

_NOT_ALPHANUMERIC = re.compile(r"[^0-9a-z]+")


def normalize_name(name: str) -> str:
    """The form two names must share to be the same.

    Lowercase, without accents, with any sign turned into a space and spaces collapsed, so
    "Café  Martínez" and "cafe-martinez" match.
    """
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _NOT_ALPHANUMERIC.sub(" ", plain).strip()
