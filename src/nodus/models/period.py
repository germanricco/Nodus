"""Calendar periods used to group transactions, and how they are written in each language."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from nodus.i18n import N_, _
from nodus.models.language_format import current_format

# Translated where shown (month_name), in the language Nodus is in by then.
MONTH_NAMES = [
    N_("Enero"), N_("Febrero"), N_("Marzo"), N_("Abril"), N_("Mayo"), N_("Junio"),
    N_("Julio"), N_("Agosto"), N_("Septiembre"), N_("Octubre"), N_("Noviembre"), N_("Diciembre"),
]  # fmt: skip

# The days a date can take: room for old records and long plans, while every date
# computed from one (the next charge, the last installment) stays a valid date.
FIRST_DAY = date(1900, 1, 1)
LAST_DAY = date(2100, 12, 31)


def format_date(day: date) -> str:
    """The whole date: "05/11/2026" in Spanish, "11/05/2026" in English."""
    return day.strftime(current_format().date)


def qt_date_format() -> str:
    """The whole date as a date field writes it, in Qt's terms: "dd/MM/yyyy"."""
    return current_format().qt_date


def format_day_month(day: date) -> str:
    """Day and month, where the year goes without saying: "05/11" (or "11/05")."""
    return day.strftime(current_format().day_month)


def month_name(month: int) -> str:
    """ "Noviembre", or "November": the name of month 1 to 12 as it starts a title."""
    return _(MONTH_NAMES[month - 1])


def format_month(month: Month) -> str:
    """Month name and year, as a title: "Noviembre 2026"."""
    return f"{month_name(month.month)} {month.year}"


def format_month_in_sentence(month: Month) -> str:
    """Month and year inside a sentence: "octubre de 2027", "October 2027"."""
    language = current_format()
    name = month_name(month.month)
    return language.month_in_sentence.format(
        month=name.lower() if language.lowercase_months else name, year=month.year
    )


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
        return month_name(self.month)[:3]

    def day(self, day_of_month: int) -> date:
        """That day of this month, or its last day when the month is shorter: what a monthly
        payment set on the 31st falls on in February."""
        return self.start.replace(day=min(day_of_month, self.end.day))

    def months_to(self, other: Month) -> int:
        """Whole months from this month to ``other``: 4 from November to March; negative
        when ``other`` comes before."""
        return (other.year - self.year) * 12 + other.month - self.month

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
        """Whether it runs from a 1st to a month's last day, so it can be compared month by
        month."""
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
        count = first.months_to(last) + 1
        return [first.shifted(i) for i in range(count)]

    def months_since(self, first_day: date, today: date) -> list[Month]:
        """The months of the period with a history: from the one of ``first_day`` (the
        first movement) through the current one.

        A month before the first movement, or still to come, is not a month without
        spending: there is nothing to know about it yet, so it does not count in an average.
        """
        first, current = Month.of(first_day), Month.of(today)
        return [month for month in self.months() if first <= month <= current]

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
    """The ready-made periods offered by the period selector; the value is the name,
    marked for translation."""

    CURRENT_MONTH = N_("Mes actual")
    LAST_3_MONTHS = N_("Últimos 3 meses")
    LAST_6_MONTHS = N_("Últimos 6 meses")
    LAST_12_MONTHS = N_("Últimos 12 meses")
    THIS_YEAR = N_("Este año")
    PREVIOUS_YEAR = N_("Año anterior")

    @property
    def label(self) -> str:
        """Its name in the language Nodus is in."""
        return _(self.value)

    def period(self, today: date) -> Period:
        """The days this choice covers as seen from ``today``."""
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
