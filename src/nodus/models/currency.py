"""Currencies supported by Nodus."""

from enum import Enum


class Currency(Enum):
    """A currency an account can hold. The value is its ISO 4217 code, as stored in the database."""

    ARS = "ARS"
    USD = "USD"
    EUR = "EUR"
    CLP = "CLP"

    @property
    def symbol(self) -> str:
        """Symbol shown before amounts. USD uses "US$" and CLP "CLP$", so neither is ever
        confused with pesos."""
        return _SYMBOLS[self]

    @property
    def decimals(self) -> int:
        """Digits after the decimal comma: the Chilean peso has no cents."""
        return 0 if self is Currency.CLP else 2

    @property
    def is_foreign(self) -> bool:
        """Every currency but the peso, which needs an exchange rate to be added up."""
        return self is not HOME_CURRENCY


_SYMBOLS = {Currency.ARS: "$", Currency.USD: "US$", Currency.EUR: "€", Currency.CLP: "CLP$"}

# Every exchange rate is stored against the peso; other pairs go through it.
HOME_CURRENCY = Currency.ARS
# The net worth adds up in these; amounts in the others are converted into them.
TOTAL_CURRENCIES = (Currency.ARS, Currency.USD)
FOREIGN_CURRENCIES = tuple(c for c in Currency if c is not HOME_CURRENCY)
