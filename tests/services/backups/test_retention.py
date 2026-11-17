"""How long each copy is kept: what a year of copies comes down to, day by day."""

from datetime import date, timedelta

import pytest

from nodus.services.backups.retention import (
    DAILY,
    MONTHLY,
    ONE_OFF_DAYS,
    WEEKLY,
    kept_days,
    one_off_expired,
)

TODAY = date(2026, 11, 17)


def every_day(count: int, last: date = TODAY) -> list[date]:
    return [last - timedelta(days=n) for n in range(count)]


def test_the_newest_three_days_are_kept():
    kept = kept_days(every_day(3))

    assert kept == set(every_day(3))


def test_a_year_of_daily_use_keeps_13_copies_reaching_half_a_year_back():
    kept = sorted(kept_days(every_day(365)))

    assert len(kept) <= DAILY + WEEKLY + MONTHLY == 13  # a Sunday can be daily and weekly
    assert kept[-DAILY:] == sorted(every_day(DAILY))
    assert kept[0] == date(2026, 5, 31)  # the end of the sixth month before this one


def test_the_weeks_and_months_before_this_one_keep_their_last_copy():
    kept = kept_days(every_day(365))

    assert date(2026, 11, 15) in kept  # the Sunday that closed last week
    assert date(2026, 10, 31) in kept  # the last day of last month
    assert date(2026, 11, 13) not in kept


def test_a_copy_kept_for_its_week_stays_as_days_go_by():
    """The kept copies do not move every day: a closed week's copy is the same tomorrow."""
    today = kept_days(every_day(365))
    tomorrow = kept_days(every_day(366, TODAY + timedelta(days=1)))

    assert date(2026, 11, 15) in today & tomorrow


def test_someone_who_opens_nodus_once_a_month_keeps_half_a_year():
    monthly = [date(2026, month, 3) for month in range(1, 12)]

    kept = kept_days(monthly)

    assert min(kept) == date(2026, 5, 3)
    assert len(kept) == 7  # this month's and the six before


def test_no_copies_keep_nothing():
    assert kept_days([]) == set()


@pytest.mark.parametrize(("age", "expired"), [(0, False), (ONE_OFF_DAYS, False), (31, True)])
def test_a_copy_before_restoring_or_deleting_lasts_a_month(age, expired):
    assert one_off_expired(TODAY - timedelta(days=age), TODAY) is expired
