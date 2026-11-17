"""Reading an amount as people type it in Argentina, without guessing.

The form fields read amounts here, and so will any other way of typing one in (Telegram,
in a later version), so every one of them takes the same text the same way. A text that
could mean two amounts is refused with a message that shows how to write it, because a
guess that reads «1,234» as one thousand and not as one with decimals moves a balance
without the user noticing.
"""

from __future__ import annotations

import re
from decimal import Decimal

from nodus.models.currency import Currency
from nodus.models.money import MAX_UNITS, Money

MAX_DECIMALS = 2
TOO_LARGE_TEXT = "El monto es demasiado grande."
COMMA_FOR_DECIMALS_TEXT = "Usa coma para los decimales: 1.234,56."
TOO_MANY_DECIMALS_TEXT = f"Un monto lleva hasta {MAX_DECIMALS} decimales, como en 1.234,56."
DOTS_GROUP_THOUSANDS_TEXT = "Los puntos separan los miles, de a tres cifras: 1.234.567."

_CHARACTERS = re.compile(r"^-?[\d.,]+$")
# Dots that group thousands: 1.234 or 12.345.678, never 1.23 or 1234.567.
_GROUPED = re.compile(r"^\d{1,3}(\.\d{3})+$")
# A lone dot before one or two digits is a decimal point, as many people type "12.50".
_DOT_DECIMALS = re.compile(r"^\d*\.\d{1,2}$")


class AmountTextError(ValueError):
    """The text is not an amount. The message, in Spanish, says why to the user."""


def without_cents_text(currency: Currency) -> str:
    """«Los pesos chilenos no llevan centavos.»"""
    return f"Los {currency.name_plural} no llevan centavos."


def parse_amount(text: str, currency: Currency) -> Money:
    """The amount ``text`` means in ``currency``.

    The comma is the decimal separator and the dot groups thousands ("1.234,56"); a lone
    dot before one or two digits is also read as a decimal point ("12.50"). Raises
    ``AmountTextError`` when the text is not an amount or could mean more than one:
    a dot after the comma, more than two decimals, dots that do not group by three, or
    cents in a currency without them.
    """
    shown = text.strip()
    cleaned = shown.replace(" ", "").replace("\N{NO-BREAK SPACE}", "")
    if not _CHARACTERS.match(cleaned) or not any(c.isdigit() for c in cleaned):
        raise AmountTextError(f"«{shown}» no es un monto válido.")
    sign = "-" if cleaned.startswith("-") else ""
    units, decimals = _split(cleaned.removeprefix("-"))
    if len(decimals) > MAX_DECIMALS:
        raise AmountTextError(TOO_MANY_DECIMALS_TEXT)
    value = Decimal(f"{sign}{units or 0}.{decimals or 0}")
    if abs(value) > MAX_UNITS:
        raise AmountTextError(TOO_LARGE_TEXT)
    if not currency.decimals and value != value.to_integral_value():
        raise AmountTextError(without_cents_text(currency))
    return Money.from_decimal(value, currency)


def _split(number: str) -> tuple[str, str]:
    """The digits before and after the decimal separator, thousands dots removed."""
    if "," in number:
        units, _, decimals = number.partition(",")
        if "," in decimals or "." in decimals:
            raise AmountTextError(COMMA_FOR_DECIMALS_TEXT)
        return _ungrouped(units), decimals
    if _DOT_DECIMALS.match(number):
        units, _, decimals = number.partition(".")
        return units, decimals
    return _ungrouped(number), ""


def _ungrouped(units: str) -> str:
    """``units`` without the dots that group its thousands; rejects dots out of place."""
    if "." not in units:
        return units
    if not _GROUPED.match(units):
        raise AmountTextError(DOTS_GROUP_THOUSANDS_TEXT)
    return units.replace(".", "")
