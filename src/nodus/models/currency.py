"""Currencies supported by Nodus, and what each one is: the single place to add one."""

from dataclasses import dataclass
from enum import Enum


class Currency(Enum):
    """A currency an account can hold. The value is its ISO 4217 code, as stored in the database.

    The order is the order everywhere: menus, and the series of the charts.
    """

    ARS = "ARS"
    USD = "USD"
    EUR = "EUR"
    CLP = "CLP"

    @property
    def symbol(self) -> str:
        """Symbol shown before amounts. USD uses "US$" and CLP "CLP$", so neither is ever
        confused with pesos."""
        return _DETAILS[self].symbol

    @property
    def decimals(self) -> int:
        """Digits after the decimal comma: the Chilean peso has no cents."""
        return _DETAILS[self].decimals

    @property
    def name_singular(self) -> str:
        """Its name in a sentence, as in «Sin cotización del dólar»."""
        return _DETAILS[self].singular

    @property
    def name_plural(self) -> str:
        """Its name for amounts held in it, as in «Tus cuentas en dólares»."""
        return _DETAILS[self].plural

    @property
    def is_foreign(self) -> bool:
        """Every currency but the peso, which needs an exchange rate to be added up."""
        return self is not HOME_CURRENCY


@dataclass(frozen=True)
class _Details:
    symbol: str
    decimals: int
    singular: str
    plural: str


_DETAILS = {
    Currency.ARS: _Details("$", 2, "peso", "pesos"),
    Currency.USD: _Details("US$", 2, "dólar", "dólares"),
    Currency.EUR: _Details("€", 2, "euro", "euros"),
    Currency.CLP: _Details("CLP$", 0, "peso chileno", "pesos chilenos"),
}

# Every exchange rate is stored against the peso; other pairs go through it.
HOME_CURRENCY = Currency.ARS
# The net worth adds up in these; amounts in the others are converted into them.
TOTAL_CURRENCIES = (Currency.ARS, Currency.USD)
FOREIGN_CURRENCIES = tuple(c for c in Currency if c is not HOME_CURRENCY)
