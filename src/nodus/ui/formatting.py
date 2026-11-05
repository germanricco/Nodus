"""Formatting of values for display."""

from datetime import date


def format_date(day: date) -> str:
    """Day/month/year, as dates are written in Argentina: "05/11/2026"."""
    return day.strftime("%d/%m/%Y")
