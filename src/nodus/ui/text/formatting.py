"""Formatting of values for display. Date and month formats live in models, so services can
use them too; they are re-exported here for the interface."""

from nodus.models.money import Money
from nodus.models.period import format_date, format_month

__all__ = ["format_date", "format_month"]


def percent(part: Money, whole: Money) -> str:
    """Share of ``whole``, rounded to a whole percent; "—" when ``whole`` is not positive."""
    return rate_text(part.cents / whole.cents if whole.cents > 0 else None)


def rate_text(share: float | None) -> str:
    """A share (0.2 is 20 %) rounded to a whole percent, as a savings rate; "—" without
    one."""
    return "—" if share is None else f"{round(100 * share)} %"
