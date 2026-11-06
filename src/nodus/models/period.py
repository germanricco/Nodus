"""Calendar periods used to group transactions, and how they are written in Spanish."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]  # fmt: skip
SHORT_MONTH_NAMES = [name[:3] for name in MONTH_NAMES]


def format_date(day: date) -> str:
    """Day/month/year, as dates are written in Argentina: "05/11/2026"."""
    return day.strftime("%d/%m/%Y")


def format_month(month: Month) -> str:
    """Month name and year, e.g. "Noviembre 2026"."""
    return f"{MONTH_NAMES[month.month - 1]} {month.year}"


@dataclass(frozen=True, order=True)
class Month:
    """A calendar month, the unit in which personal finances are usually reviewed."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError(f"Invalid month: {self.month}")

    @classmethod
    def of(cls, day: date) -> Month:
        return cls(day.year, day.month)

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def end(self) -> date:
        """Last day of the month, inclusive."""
        return date(self.year, self.month, calendar.monthrange(self.year, self.month)[1])

    @property
    def short_name(self) -> str:
        """ "Nov", for chart axes."""
        return SHORT_MONTH_NAMES[self.month - 1]

    def shifted(self, months: int) -> Month:
        """The month ``months`` away (negative goes back)."""
        index = self.year * 12 + self.month - 1 + months
        return Month(index // 12, index % 12 + 1)

    def next(self) -> Month:
        return self.shifted(1)

    def previous(self) -> Month:
        return self.shifted(-1)


@dataclass(frozen=True)
class Period:
    """A range of days, both ends included: what the dashboard and the transaction list show.

    Periods made of whole months (the usual case) move and compare by months, so the
    previous period of "Sep – Nov" is "Jun – Ago" and not 91 days back.
    """

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("A period cannot end before it starts")

    @classmethod
    def of_months(cls, first: Month, last: Month | None = None) -> Period:
        return cls(first.start, (last or first).end)

    @classmethod
    def last_months(cls, count: int, today: date) -> Period:
        """The last ``count`` months, the current one included."""
        current = Month.of(today)
        return cls.of_months(current.shifted(1 - count), current)

    @classmethod
    def year(cls, year: int) -> Period:
        return cls(date(year, 1, 1), date(year, 12, 31))

    @property
    def is_whole_months(self) -> bool:
        return self.start.day == 1 and self.end == Month.of(self.end).end

    @property
    def first_month(self) -> Month:
        return Month.of(self.start)

    @property
    def last_month(self) -> Month:
        return Month.of(self.end)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def months(self) -> list[Month]:
        """Every month the period touches, oldest first."""
        first, last = self.first_month, self.last_month
        count = (last.year - first.year) * 12 + last.month - first.month + 1
        return [first.shifted(i) for i in range(count)]

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def shifted(self, steps: int) -> Period:
        """The period of the same length ``steps`` lengths away (negative goes back)."""
        if self.is_whole_months:
            length = len(self.months())
            return Period.of_months(
                self.first_month.shifted(steps * length), self.last_month.shifted(steps * length)
            )
        offset = timedelta(days=steps * self.days)
        return Period(self.start + offset, self.end + offset)

    def previous(self) -> Period:
        """The period of the same length right before, to compare with."""
        return self.shifted(-1)

    def label(self) -> str:
        """ "Noviembre 2026", "2026" for a whole year, "Sep – Nov 2026" or "Nov 2025 – Ene 2026"."""
        first, last = self.first_month, self.last_month
        if not self.is_whole_months:
            return f"{format_date(self.start)} – {format_date(self.end)}"
        if first == last:
            return format_month(first)
        if first.month == 1 and last.month == 12 and first.year == last.year:
            return str(first.year)
        if first.year == last.year:
            return f"{first.short_name} – {last.short_name} {last.year}"
        return f"{first.short_name} {first.year} – {last.short_name} {last.year}"


class QuickPeriod(Enum):
    """The ready-made periods offered by the period selector, with their Spanish name."""

    CURRENT_MONTH = "Mes actual"
    LAST_3_MONTHS = "Últimos 3 meses"
    LAST_6_MONTHS = "Últimos 6 meses"
    LAST_12_MONTHS = "Últimos 12 meses"
    THIS_YEAR = "Este año"
    PREVIOUS_YEAR = "Año anterior"

    def period(self, today: date) -> Period:
        if self is QuickPeriod.THIS_YEAR:
            return Period.year(today.year)
        if self is QuickPeriod.PREVIOUS_YEAR:
            return Period.year(today.year - 1)
        return Period.last_months(_MONTH_COUNTS[self], today)


_MONTH_COUNTS = {
    QuickPeriod.CURRENT_MONTH: 1,
    QuickPeriod.LAST_3_MONTHS: 3,
    QuickPeriod.LAST_6_MONTHS: 6,
    QuickPeriod.LAST_12_MONTHS: 12,
}
