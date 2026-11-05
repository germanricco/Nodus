"""Formatting of values for display."""

from datetime import date

from nodus.models.period import Month

_MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]  # fmt: skip


def format_date(day: date) -> str:
    """Day/month/year, as dates are written in Argentina: "05/11/2026"."""
    return day.strftime("%d/%m/%Y")


def format_month(month: Month) -> str:
    """Month name and year, e.g. "Noviembre 2026"."""
    return f"{_MONTH_NAMES[month.month - 1]} {month.year}"
