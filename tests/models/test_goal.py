from datetime import date

import pytest
from factories import usd

from nodus.models.goal import Goal, GoalShare, GoalState, goal_progress, median_cents, months_until
from nodus.models.period import Month

TODAY = date(2026, 11, 13)


def goal(target="2000", on=date(2027, 3, 31), reached_on=None) -> Goal:
    return Goal(1, "Vacaciones", usd(target), on, (GoalShare(1, 100),), reached_on)


def ends(*amounts) -> list:
    return [usd(a) for a in amounts]


def test_months_until():
    assert months_until(TODAY, date(2027, 3, 1)) == 4
    assert months_until(TODAY, date(2026, 11, 30)) == 0


@pytest.mark.parametrize(
    ("values", "median"), [([3], 3), ([1, 9, 5], 5), ([1, 2, 3, 10], 2), ([10, 0], 5)]
)
def test_median(values, median):
    assert median_cents(values) == median


def test_on_track():
    progress = goal_progress(goal(), usd("820"), ends("0", "300", "600", "800"), TODAY)

    assert progress.state is GoalState.ON_TRACK
    assert progress.remaining == usd("1180")
    assert progress.needed_per_month == usd("295")  # 4 months to March
    assert progress.pace_per_month == usd("300")  # the median of 300, 300 and 200
    assert progress.eta == Month(2027, 3)  # 1180 / 300, rounded up: 4 months
    assert progress.month_change == usd("20")
    assert progress.percent == 41


def test_behind_when_the_pace_arrives_after_the_date():
    progress = goal_progress(goal(), usd("820"), ends("400", "500", "600", "700"), TODAY)

    assert progress.state is GoalState.BEHIND
    assert progress.eta == Month(2027, 11)  # 1180 / 100: 12 months


def test_behind_with_a_slow_pace():
    progress = goal_progress(goal(), usd("820"), ends("700", "720", "740", "760"), TODAY)

    assert progress.state is GoalState.BEHIND
    assert progress.eta == Month(2026, 11).shifted(59)  # 1180 / 20


def test_behind_when_savings_go_down():
    progress = goal_progress(goal(), usd("820"), ends("900", "880", "850", "830"), TODAY)

    assert (progress.state, progress.eta) == (GoalState.BEHIND, None)


def test_no_history_with_fewer_than_three_changes():
    progress = goal_progress(goal(), usd("820"), ends("500", "700", "800"), TODAY)

    assert progress.state is GoalState.NO_HISTORY
    assert progress.pace_per_month is None
    assert progress.needed_per_month == usd("295")


def test_without_a_date():
    progress = goal_progress(goal(on=None), usd("820"), ends("400", "500", "600", "700"), TODAY)

    assert progress.state is GoalState.NO_DATE
    assert progress.needed_per_month is None


def test_overdue():
    progress = goal_progress(goal(on=date(2026, 10, 31)), usd("820"), ends(), TODAY)

    assert progress.state is GoalState.OVERDUE


def test_needs_everything_in_its_last_month():
    progress = goal_progress(goal(on=date(2026, 11, 30)), usd("820"), ends(), TODAY)

    assert progress.needed_per_month == usd("1180")


def test_reached_by_its_balance():
    progress = goal_progress(goal(), usd("2100"), ends(), TODAY)

    assert progress.state is GoalState.REACHED
    assert progress.remaining == usd("0")
    assert progress.percent == 105


def test_stays_reached_once_spent():
    progress = goal_progress(goal(reached_on=date(2026, 10, 1)), usd("100"), ends(), TODAY)

    assert progress.state is GoalState.REACHED
    assert progress.percent == 5


def test_almost_is_not_a_hundred_percent():
    assert goal_progress(goal(), usd("1999.99"), ends(), TODAY).percent == 99


def test_without_a_rate():
    progress = goal_progress(goal(), None, ends(), TODAY)

    assert (progress.state, progress.saved, progress.percent) == (GoalState.NO_RATE, None, 0)
