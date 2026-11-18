"""Reading an amount as people type it, in the language Nodus is in, without guessing.

The form fields read amounts here, and so will any other way of typing one in (Telegram,
in a later version), so every one of them takes the same text the same way. A text that
could mean two amounts is refused with a message that shows how to write it, because a
guess that reads «1,234» as one thousand and not as one with decimals moves a balance
without the user noticing.

The rules are the same in every language, with its own separators (``language_format``):
in Spanish the comma is decimal and the dot groups thousands, in English the other way
round, so an amount is typed the way Nodus shows it.
"""

from __future__ import annotations

import re
from decimal import Decimal

from nodus.i18n import N_, _
from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.models.language_format import current_format, grouped
from nodus.models.money import MAX_UNITS, Money

MAX_DECIMALS = 2

_TOO_LARGE = N_("El monto es demasiado grande.")
_NOT_AN_AMOUNT = N_("«{text}» no es un monto válido.")
_DECIMAL_SEPARATOR = N_("Usa coma para los decimales: {example}.")
_TOO_MANY_DECIMALS = N_("Un monto lleva hasta {decimals} decimales, como en {example}.")
_GROUPING = N_("Los puntos separan los miles, de a tres cifras: {example}.")
_WITHOUT_CENTS = N_("Los {currency} no llevan centavos.")

_CHARACTERS = re.compile(r"^-?[\d.,]+$")


class AmountTextError(ValueError):
    """The text is not an amount. The message, in the user's language, says why."""


def too_large_text() -> str:
    """«El monto es demasiado grande.»"""
    return _(_TOO_LARGE)


def decimal_separator_text() -> str:
    """«Usa coma para los decimales: 1.234,56.»"""
    return _(_DECIMAL_SEPARATOR).format(example=_example())


def too_many_decimals_text() -> str:
    """«Un monto lleva hasta 2 decimales, como en 1.234,56.»"""
    return _(_TOO_MANY_DECIMALS).format(decimals=MAX_DECIMALS, example=_example())


def grouping_text() -> str:
    """«Los puntos separan los miles, de a tres cifras: 1.234.567.»"""
    return _(_GROUPING).format(example=grouped(1_234_567))


def without_cents_text(currency: Currency) -> str:
    """«Los pesos chilenos no llevan centavos.»"""
    return _(_WITHOUT_CENTS).format(currency=currency.name_plural)


def _example() -> str:
    """An amount with thousands and cents, as the language writes it: «1.234,56»."""
    return Money(123_456, HOME_CURRENCY).format_number()


def parse_amount(text: str, currency: Currency) -> Money:
    """The amount ``text`` means in ``currency``.

    The language's decimal separator splits units from cents and its thousands separator
    groups the units by three ("1.234,56" in Spanish, "1,234.56" in English); a lone
    thousands separator before one or two digits is also read as decimal ("12.50" in
    Spanish), as many people type it. Raises ``AmountTextError`` when the text is not an
    amount or could mean more than one: a separator after the decimal one, more than two
    decimals, groups that are not of three, or cents in a currency without them.
    """
    shown = text.strip()
    cleaned = shown.replace(" ", "").replace("\N{NO-BREAK SPACE}", "")
    if not _CHARACTERS.match(cleaned) or not any(c.isdigit() for c in cleaned):
        raise AmountTextError(_(_NOT_AN_AMOUNT).format(text=shown))
    sign = "-" if cleaned.startswith("-") else ""
    units, decimals = _split(cleaned.removeprefix("-"))
    if len(decimals) > MAX_DECIMALS:
        raise AmountTextError(too_many_decimals_text())
    value = Decimal(f"{sign}{units or 0}.{decimals or 0}")
    if abs(value) > MAX_UNITS:
        raise AmountTextError(too_large_text())
    if not currency.decimals and value != value.to_integral_value():
        raise AmountTextError(without_cents_text(currency))
    return Money.from_decimal(value, currency)


def _split(number: str) -> tuple[str, str]:
    """The digits before and after the decimal separator, thousands separators removed."""
    language = current_format()
    decimal, thousands = language.decimal, language.thousands
    if decimal in number:
        units, _separator, decimals = number.partition(decimal)
        if decimal in decimals or thousands in decimals:
            raise AmountTextError(decimal_separator_text())
        return _ungrouped(units, thousands), decimals
    # A lone thousands separator before one or two digits is a decimal one: «12.50».
    if re.fullmatch(rf"\d*{re.escape(thousands)}\d{{1,2}}", number):
        units, _separator, decimals = number.partition(thousands)
        return units, decimals
    return _ungrouped(number, thousands), ""


def _ungrouped(units: str, thousands: str) -> str:
    """``units`` without the separators that group them; rejects separators out of place
    (groups of three only: 1.234 or 12.345.678, never 1.23 or 1234.567)."""
    if thousands not in units:
        return units
    if not re.fullmatch(rf"\d{{1,3}}({re.escape(thousands)}\d{{3}})+", units):
        raise AmountTextError(grouping_text())
    return units.replace(thousands, "")
