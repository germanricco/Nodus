"""Formatting of values for display. ``format_date`` lives in models, so services can use it
too; it is re-exported here for the interface."""

from nodus.models.period import Month, format_date

__all__ = ["format_date", "format_month"]

_MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]  # fmt: skip


def format_month(month: Month) -> str:
    """Month name and year, e.g. "Noviembre 2026"."""
    return f"{_MONTH_NAMES[month.month - 1]} {month.year}"
