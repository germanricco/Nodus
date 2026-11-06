from datetime import date

import pytest
from factories import ars

from nodus.models.recurring_charge import DueStatus, Frequency, RecurringCharge, next_due

TODAY = date(2026, 11, 6)


def charge(frequency=Frequency.MONTHLY, due=TODAY, amount="1200", anchor_day=None):
    return RecurringCharge(
        None, "Netflix", ars(amount), 1, 1, frequency, anchor_day or due.day, due
    )


@pytest.mark.parametrize(
    ("day", "frequency", "expected"),
    [
        (date(2026, 11, 6), Frequency.WEEKLY, date(2026, 11, 13)),
        (date(2026, 12, 25), Frequency.BIWEEKLY, date(2027, 1, 8)),
        (date(2026, 11, 6), Frequency.MONTHLY, date(2026, 12, 6)),
        (date(2026, 11, 6), Frequency.QUARTERLY, date(2027, 2, 6)),
        (date(2026, 11, 6), Frequency.SEMIANNUAL, date(2027, 5, 6)),
        (date(2026, 11, 6), Frequency.ANNUAL, date(2027, 11, 6)),
    ],
)
def test_next_due_for_every_frequency(day, frequency, expected):
    assert next_due(day, frequency, day.day) == expected


def test_a_charge_on_the_31st_returns_to_the_31st_after_short_months():
    day, dates = date(2027, 1, 31), []
    for _ in range(3):
        day = next_due(day, Frequency.MONTHLY, 31)
        dates.append(day)
    assert dates == [date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]


def test_february_29th_in_a_leap_year():
    assert next_due(date(2028, 1, 31), Frequency.MONTHLY, 31) == date(2028, 2, 29)
    assert next_due(date(2028, 2, 29), Frequency.ANNUAL, 29) == date(2029, 2, 28)


@pytest.mark.parametrize(
    ("frequency", "monthly"),
    [
        (Frequency.WEEKLY, "5200"),
        (Frequency.BIWEEKLY, "2600"),
        (Frequency.MONTHLY, "1200"),
        (Frequency.QUARTERLY, "400"),
        (Frequency.SEMIANNUAL, "200"),
        (Frequency.ANNUAL, "100"),
    ],
)
def test_monthly_amount(frequency, monthly):
    assert charge(frequency).monthly_amount() == ars(monthly)


def test_monthly_amount_rounds_to_the_cent():
    assert charge(Frequency.ANNUAL, amount="100").monthly_amount() == ars("8.33")


@pytest.mark.parametrize(
    ("due", "status", "days"),
    [
        (date(2026, 11, 5), DueStatus.OVERDUE, -1),
        (TODAY, DueStatus.SOON, 0),
        (date(2026, 11, 13), DueStatus.SOON, 7),
        (date(2026, 11, 14), DueStatus.LATER, 8),
    ],
)
def test_status_against_today(due, status, days):
    assert charge(due=due).status(TODAY) is status
    assert charge(due=due).days_until(TODAY) == days


def test_following_due_keeps_the_anchor_day():
    assert charge(due=date(2027, 2, 28), anchor_day=31).following_due() == date(2027, 3, 31)


def test_rejects_non_positive_amounts_and_invalid_days():
    with pytest.raises(ValueError):
        charge(amount="0")
    with pytest.raises(ValueError):
        charge(anchor_day=32)
