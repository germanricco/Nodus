"""How long each copy is kept.

The daily copies answer two different needs. A damaged file needs the newest healthy
copy, so the last few days are kept. A mistake noticed late (an account deleted a month
ago) needs an older one, so one copy of each recent week and month is kept as well: 13
files at most, reaching half a year back. A copy taken before restoring or deleting
answers one moment only, and goes after a month.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from datetime import date

DAILY = 3
WEEKLY = 4
MONTHLY = 6
ONE_OFF_DAYS = 30


def kept_days(days: list[date]) -> set[date]:
    """The days whose daily copy stays: the newest ``DAILY``, and the newest copy of each
    of the ``WEEKLY`` weeks and ``MONTHLY`` months before the current one that have one.
    A week's newest copy never changes once the week is over, so the one kept does not
    move every day; the current week and month are already in the daily ones."""
    newest_first = sorted(set(days), reverse=True)
    return (
        set(newest_first[:DAILY])
        | _newest_of_each(newest_first, lambda day: day.isocalendar()[:2], WEEKLY)
        | _newest_of_each(newest_first, lambda day: (day.year, day.month), MONTHLY)
    )


def one_off_expired(saved_on: date, today: date) -> bool:
    """Whether a copy taken before restoring or deleting has served its month."""
    return (today - saved_on).days > ONE_OFF_DAYS


def _newest_of_each(
    newest_first: list[date], period: Callable[[date], Hashable], count: int
) -> set[date]:
    """The newest day of each of ``count`` periods before the newest day's own."""
    current = period(newest_first[0]) if newest_first else None
    newest: dict[Hashable, date] = {}
    for day in newest_first:
        key = period(day)
        if key != current and key not in newest:
            if len(newest) == count:
                break
            newest[key] = day
    return set(newest.values())
