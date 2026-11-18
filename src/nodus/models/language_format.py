"""How each language writes numbers, amounts, percentages and dates.

Every figure Nodus shows goes through here, so that each language writes them its own
way: «$ 1.234,56», «48 %» and «18/11/2026» in Spanish, «$1,234.56», «48%» and
«11/18/2026» in English. Amounts are typed the same way they are shown
(``amount_parsing``), so a figure copied from a screen reads back as it was. The
currency symbols are the same in both languages.
"""

from __future__ import annotations

from dataclasses import dataclass

from nodus.i18n import Language, current_language


@dataclass(frozen=True)
class LanguageFormat:
    """The way one language writes figures."""

    decimal: str  # between units and cents
    thousands: str  # groups the units by three
    space: str  # between a symbol and its number, and between a number and «%»
    thousand_suffix: str  # «15 k» or «15K», on chart axes
    date: str  # the whole date, for strftime
    day_month: str  # where the year goes without saying
    qt_date: str  # the whole date as a date field writes it, for Qt
    month_in_sentence: str  # a month and its year inside a sentence: «octubre de 2027»
    lowercase_months: bool  # inside a sentence: Spanish does, English never
    csv_separator: str  # between columns, as Excel in that language expects


FORMATS = {
    Language.SPANISH: LanguageFormat(
        decimal=",",
        thousands=".",
        space=" ",
        thousand_suffix="k",
        date="%d/%m/%Y",
        day_month="%d/%m",
        qt_date="dd/MM/yyyy",
        month_in_sentence="{month} de {year}",
        lowercase_months=True,
        csv_separator=";",
    ),
    Language.ENGLISH: LanguageFormat(
        decimal=".",
        thousands=",",
        space="",
        thousand_suffix="K",
        date="%m/%d/%Y",
        day_month="%m/%d",
        qt_date="MM/dd/yyyy",
        month_in_sentence="{month} {year}",
        lowercase_months=False,
        csv_separator=",",
    ),
}


def current_format() -> LanguageFormat:
    """The format of the language Nodus is in now."""
    return FORMATS[current_language()]


def grouped(units: int) -> str:
    """Whole units grouped by three: «1.234.567» or «1,234,567»."""
    return f"{units:,}".replace(",", current_format().thousands)


def format_decimal(value: float, decimals: int, drop_zero: bool = False) -> str:
    """``value`` with ``decimals`` digits after the language's separator: «9,5» or «9.5».
    With ``drop_zero``, a whole value shows none: «12», not «12,0»."""
    text = f"{value:.{decimals}f}"
    if drop_zero and decimals and set(text.partition(".")[2]) == {"0"}:
        text = text.partition(".")[0]
    return text.replace(".", current_format().decimal)


def format_percent(number: int | str) -> str:
    """A percentage: «48 %» or «48%». ``number`` comes already written («<1», «9,5»)."""
    return f"{number}{current_format().space}%"


def with_symbol(symbol: str, number: str) -> str:
    """A currency symbol and what follows it: «US$ 10,00» or «US$10.00», «US$ ••••»."""
    return f"{symbol}{current_format().space}{number}"
