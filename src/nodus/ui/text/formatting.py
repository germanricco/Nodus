"""Formatting of values for display. Date and month formats live in models, so services can
use them too; they are re-exported here for the interface."""

from nodus.models.language_format import format_percent, with_symbol
from nodus.models.money import Money
from nodus.models.period import format_date, format_month

__all__ = ["format_date", "format_month"]


def sign(negative: bool) -> str:
    """The sign every change shows, also a positive one: "-" or "+"."""
    return "-" if negative else "+"


def unbroken(text: str) -> str:
    """``text`` with no-break spaces, for an amount in a line that wraps: «$ 180.000,00»
    stays whole instead of leaving its symbol at the end of a line."""
    return text.replace(" ", " ")


def masked(money: Money) -> str:
    """ "$ ••••": only the currency of an amount the user chose to hide."""
    return with_symbol(money.currency.symbol, "••••")


def signed(money: Money, hidden: bool = False) -> str:
    """ "+$ 118.400,00" or "-$ 2.000,00": a change always shows its sign, also when the
    amounts are hidden ("+$ ••••")."""
    if hidden:
        return f"{sign(money.is_negative)}{masked(money)}"
    return money.format() if money.is_negative else f"{sign(False)}{money.format()}"


def percent(part: Money, whole: Money) -> str:
    """Share of ``whole``, rounded to a whole percent; "—" when ``whole`` is not positive."""
    return rate_text(part.cents / whole.cents if whole.cents > 0 else None)


def rate_text(share: float | None) -> str:
    """A share (0.2 is 20 %) rounded to a whole percent, as a savings rate; "—" without
    one."""
    return "—" if share is None else format_percent(round(100 * share))
