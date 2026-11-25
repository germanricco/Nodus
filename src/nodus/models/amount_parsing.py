"""Reading an amount as people type it, in the language Nodus is in, without guessing.

The form fields read amounts here, and so will any other way of typing one in (Telegram,
in a later version), so every one of them takes the same text the same way. A text that
could mean two amounts is refused with a message that shows how to write it, because a
guess that reads «1,234» as one thousand and not as one with decimals moves a balance
without the user noticing.

The rules are the same in every language, with its own separators (``language_format``):
in Spanish the comma is decimal and the dot groups thousands, in English the other way
round, so an amount is typed the way Nodus shows it.

An amount can also be a calculation, as it often comes from one: «1.500+2.300», a dinner
split in three, «36000/3», or a tip, «8500*1,1». Each number in it is read by the same
rules, except that it may have more decimals (a factor like «1,105»); the result is
rounded to the currency's cent as every amount is (``Money.from_decimal``). It is read
by a small grammar of its own, never by ``eval``.
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
_INCOMPLETE = N_("A la cuenta «{text}» le falta algo.")
_DIVISION_BY_ZERO = N_("No se puede dividir por cero.")

_CHARACTERS = re.compile(r"^-?[\d.,]+$")
# What a calculation is made of: numbers, the four operations (also «x», «×» and «÷», as
# people write them) and parentheses.
_TOKEN = re.compile(r"[\d.,]+|[-+*/xX×÷()]")
_OPERATIONS = "+-*/xX×÷()"
_TIMES = frozenset("*xX×")
_DIVIDED = frozenset("/÷")


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

    A calculation (``is_calculation``) gives its result, or says what is missing in it.
    """
    shown = text.strip()
    cleaned = shown.replace(" ", "").replace("\N{NO-BREAK SPACE}", "")
    if is_calculation(shown):
        return _checked(_Calculation(cleaned, shown).value(), currency)
    if not _CHARACTERS.match(cleaned) or not any(c.isdigit() for c in cleaned):
        raise AmountTextError(_(_NOT_AN_AMOUNT).format(text=shown))
    sign = "-" if cleaned.startswith("-") else ""
    units, decimals = _split(cleaned.removeprefix("-"))
    if len(decimals) > MAX_DECIMALS:
        raise AmountTextError(too_many_decimals_text())
    value = Decimal(f"{sign}{units or 0}.{decimals or 0}")
    if not currency.decimals and value != value.to_integral_value():
        raise AmountTextError(without_cents_text(currency))
    return _checked(value, currency)


def is_calculation(text: str) -> bool:
    """Whether ``text`` is a calculation, not a single amount: it has an operation or a
    parenthesis besides a leading minus sign."""
    rest = text.strip().removeprefix("-")
    return any(c in _OPERATIONS for c in rest)


def _checked(value: Decimal, currency: Currency) -> Money:
    """``value`` as an amount of ``currency``, unless it is too large for one."""
    if abs(value) > MAX_UNITS:
        raise AmountTextError(too_large_text())
    return Money.from_decimal(value, currency)


class _Calculation:
    """Reads a calculation by its grammar, with the usual precedence:

    sum     = product (("+" | "-") product)*
    product = factor (("*" | "/") factor)*
    factor  = "-" factor | "(" sum ")" | number
    """

    def __init__(self, cleaned: str, shown: str) -> None:
        self._shown = shown
        self._tokens: list[str] = _TOKEN.findall(cleaned)
        if "".join(self._tokens) != cleaned:  # a character that is none of these
            raise AmountTextError(_(_NOT_AN_AMOUNT).format(text=shown))
        self._position = 0

    def value(self) -> Decimal:
        result = self._sum()
        if self._position != len(self._tokens):  # a «)» with no «(», or «2(3)»
            raise self._incomplete()
        return result

    def _sum(self) -> Decimal:
        result = self._product()
        while (token := self._peek()) in ("+", "-"):
            self._take()
            term = self._product()
            result = result + term if token == "+" else result - term
        return result

    def _product(self) -> Decimal:
        result = self._factor()
        while (token := self._peek()) is not None and (token in _TIMES or token in _DIVIDED):
            self._take()
            factor = self._factor()
            if token in _TIMES:
                result *= factor
            elif factor == 0:
                raise AmountTextError(_(_DIVISION_BY_ZERO))
            else:
                result /= factor
        return result

    def _factor(self) -> Decimal:
        token = self._take()
        if token == "-":
            if self._peek() == "-":  # «--5» is a slip, not a double negative
                raise self._incomplete()
            return -self._factor()
        if token == "(":
            result = self._sum()
            if self._take() != ")":
                raise self._incomplete()
            return result
        if token is None or not any(c.isdigit() for c in token):
            raise self._incomplete()
        units, decimals = _split(token)
        return Decimal(f"{units or 0}.{decimals or 0}")

    def _peek(self) -> str | None:
        return self._tokens[self._position] if self._position < len(self._tokens) else None

    def _take(self) -> str | None:
        token = self._peek()
        self._position += 1
        return token

    def _incomplete(self) -> AmountTextError:
        return AmountTextError(_(_INCOMPLETE).format(text=self._shown))


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
