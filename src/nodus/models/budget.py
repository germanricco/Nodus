"""Monthly spending limits per category and how a month is going against them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.models.category import Category
from nodus.models.money import Money
from nodus.models.period import Month

# Below this share of the limit a budget never counts as ahead of pace, so a rent paid on
# the 1st doesn't stay in warning all month.
PACE_FLOOR = 0.70


class BudgetState(Enum):
    ON_TRACK = "on_track"
    AHEAD = "ahead"  # spending faster than the month goes by
    OVER = "over"


def month_elapsed(month: Month, today: date) -> float:
    """How much of ``month`` has gone by on ``today``: 1 for a past month, 0 for a future
    one, and the share of days so far (today included) for the current one."""
    if month < Month.of(today):
        return 1.0
    if month > Month.of(today):
        return 0.0
    return today.day / month.end.day


def used_percent_label(used: float) -> str:
    """The share of the limit spent, as people read it: "<1 %" for a token amount, and
    never "100 %" while some money is left."""
    if 0 < used < 0.01:
        return "<1 %"
    percent = round(used * 100)
    if percent >= 100 and used < 1:
        percent = 99
    return f"{percent} %"


@dataclass(frozen=True)
class Budget:
    """A category's limit for one month and what was spent in it, both in pesos.

    ``elapsed`` is the part of the month gone by, which tells whether the spending runs
    ahead of the calendar.
    """

    category: Category
    limit: Money
    spent: Money
    elapsed: float

    @property
    def used(self) -> float:
        return self.spent.cents / self.limit.cents

    @property
    def remaining(self) -> Money:
        """What is left; negative when the limit was passed."""
        return self.limit - self.spent

    @property
    def state(self) -> BudgetState:
        if self.spent.cents > self.limit.cents:
            return BudgetState.OVER
        if self.used > max(PACE_FLOOR, self.elapsed):
            return BudgetState.AHEAD
        return BudgetState.ON_TRACK
