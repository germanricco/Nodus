"""Currencies supported by Nodus."""

from enum import Enum


class Currency(Enum):
    """A currency an account can hold. The value is its ISO 4217 code, as stored in the database."""

    ARS = "ARS"
    USD = "USD"

    @property
    def symbol(self) -> str:
        """Symbol shown before amounts. USD uses "US$" so it is never confused with pesos."""
        return _SYMBOLS[self]


_SYMBOLS = {Currency.ARS: "$", Currency.USD: "US$"}
