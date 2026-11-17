"""Formatting of values for display. Date and month formats live in models, so services can
use them too; they are re-exported here for the interface."""

from nodus.models.money import Money
from nodus.models.period import format_date, format_month

__all__ = ["format_date", "format_month"]


def percent(part: Money, whole: Money) -> str:
    """Share of ``whole``, rounded to a whole percent; "—" when ``whole`` is not positive."""
    if whole.cents <= 0:
        return "—"
    return f"{round(100 * part.cents / whole.cents)} %"
