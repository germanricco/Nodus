"""Savings goals: an amount to reach, filled by the balance of the accounts linked to it."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month

# The pace is the median of the changes between the last month ends, once there are
# enough of them to tell a habit from one good month.
PACE_CHANGES = 6
MIN_PACE_CHANGES = 3


@dataclass(frozen=True)
class GoalShare:
    """The part of an account's balance that counts for a goal, in whole percents."""

    account_id: int
    percent: int


@dataclass(frozen=True)
class Goal:
    """An amount to reach (``target``, in the goal's currency), by ``target_date`` or
    whenever. What is saved is never stored: it is the shares of the linked accounts'
    balances, so it cannot drift from them.

    ``reached_on`` is set the first day the goal is reached and stays, so a goal reached
    and then spent (the trip was taken) is still a reached goal.
    """

    id: int | None
    name: str
    target: Money
    target_date: date | None
    shares: tuple[GoalShare, ...]
    reached_on: date | None = None
    reached_seen: bool = False
    is_archived: bool = False
    position: int = 0

    @property
    def currency(self) -> Currency:
        return self.target.currency

    def share_of(self, account_id: int) -> int:
        """The percent of ``account_id`` that counts for the goal, 0 if it is not linked."""
        return next((s.percent for s in self.shares if s.account_id == account_id), 0)


class GoalState(Enum):
    """Where a goal stands, in the order it is decided."""

    REACHED = "reached"
    NO_RATE = "no_rate"  # a linked account's currency has no rate to add it up
    OVERDUE = "overdue"  # the date passed before reaching it
    NO_HISTORY = "no_history"  # fewer than three months to measure the pace
    NO_DATE = "no_date"
    BEHIND = "behind"  # at this pace it arrives after its date, or never
    ON_TRACK = "on_track"


@dataclass(frozen=True)
class GoalProgress:
    """What a goal has, what it lacks and whether the user's pace gets there in time.

    ``needed_per_month`` is what to put aside each month from now to reach it by its
    date (None without a date); ``pace_per_month`` is what the user has been putting
    aside, the median of the last months' changes (None without enough history); ``eta``
    is the month the pace reaches it; ``month_change`` how much it moved this month.
    Without a rate to add the accounts up, ``saved`` and what follows from it are None.
    """

    state: GoalState
    target: Money
    saved: Money | None
    remaining: Money | None
    needed_per_month: Money | None
    pace_per_month: Money | None
    eta: Month | None
    month_change: Money | None

    @property
    def percent(self) -> int:
        """How much of the target is saved, in whole percents (may pass 100)."""
        if self.saved is None:
            return 0
        percent = max(0, self.saved.cents) * 100 // self.target.cents
        # 99.6 % is not there yet: 100 % is shown only once it is.
        return percent if self.saved.cents >= self.target.cents else min(99, percent)


def months_until(today: date, day: date) -> int:
    """Whole calendar months from ``today``'s month to ``day``'s: 4 from November to March."""
    return (day.year - today.year) * 12 + day.month - today.month


def median_cents(values: list[int]) -> int:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) // 2  # half a cent less, at most


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def goal_progress(
    goal: Goal, saved: Money | None, month_ends: list[Money], today: date
) -> GoalProgress:
    """Where ``goal`` stands on ``today`` with ``saved`` in it.

    ``month_ends`` holds what was saved at the end of each past month, oldest first, the
    last one being last month's; months before the accounts had data are left out.
    """
    if saved is None:
        state = GoalState.REACHED if goal.reached_on else GoalState.NO_RATE
        return GoalProgress(state, goal.target, None, None, None, None, None, None)
    currency = goal.currency
    remaining = Money(max(0, goal.target.cents - saved.cents), currency)
    month_change = saved - month_ends[-1] if month_ends else None

    needed = None
    if goal.target_date is not None and not remaining.is_zero:
        months_left = months_until(today, goal.target_date)
        needed = (
            Money(_ceil_div(remaining.cents, months_left), currency)
            if months_left >= 1
            else remaining
        )

    recent = month_ends[-(PACE_CHANGES + 1) :]
    changes = [b.cents - a.cents for a, b in itertools.pairwise(recent)]
    pace = Money(median_cents(changes), currency) if len(changes) >= MIN_PACE_CHANGES else None

    this_month = Month.of(today)
    eta = None
    if remaining.is_zero:
        eta = this_month
    elif pace is not None and pace.cents > 0:
        eta = this_month.shifted(_ceil_div(remaining.cents, pace.cents))

    if goal.reached_on is not None or remaining.is_zero:
        state = GoalState.REACHED
    elif goal.target_date is not None and today > goal.target_date:
        state = GoalState.OVERDUE
    elif pace is None:
        state = GoalState.NO_HISTORY
    elif goal.target_date is None:
        state = GoalState.NO_DATE
    elif eta is None or eta > Month.of(goal.target_date):
        state = GoalState.BEHIND
    else:
        state = GoalState.ON_TRACK
    return GoalProgress(state, goal.target, saved, remaining, needed, pace, eta, month_change)
