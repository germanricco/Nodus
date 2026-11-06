from datetime import date

import pytest

from nodus.models.period import Month, Period, QuickPeriod

TODAY = date(2026, 11, 6)


def test_month_shifts_across_years():
    assert Month(2026, 1).shifted(-1) == Month(2025, 12)
    assert Month(2026, 11).shifted(14) == Month(2028, 1)
    assert Month(2026, 3).previous() == Month(2026, 2)


def test_period_rejects_end_before_start():
    with pytest.raises(ValueError):
        Period(date(2026, 2, 1), date(2026, 1, 31))


@pytest.mark.parametrize(
    ("quick", "start", "end"),
    [
        (QuickPeriod.CURRENT_MONTH, date(2026, 11, 1), date(2026, 11, 30)),
        (QuickPeriod.LAST_3_MONTHS, date(2026, 9, 1), date(2026, 11, 30)),
        (QuickPeriod.LAST_6_MONTHS, date(2026, 6, 1), date(2026, 11, 30)),
        (QuickPeriod.LAST_12_MONTHS, date(2025, 12, 1), date(2026, 11, 30)),
        (QuickPeriod.THIS_YEAR, date(2026, 1, 1), date(2026, 12, 31)),
        (QuickPeriod.PREVIOUS_YEAR, date(2025, 1, 1), date(2025, 12, 31)),
    ],
)
def test_quick_periods(quick, start, end):
    assert quick.period(TODAY) == Period(start, end)


def test_months_lists_every_month_touched():
    period = Period.of_months(Month(2025, 11), Month(2026, 2))

    assert period.months() == [Month(2025, 11), Month(2025, 12), Month(2026, 1), Month(2026, 2)]


def test_previous_of_whole_months_moves_by_months():
    assert Period.of_months(Month(2026, 3)).previous() == Period.of_months(Month(2026, 2))
    assert Period.of_months(Month(2026, 9), Month(2026, 11)).previous() == Period.of_months(
        Month(2026, 6), Month(2026, 8)
    )
    assert Period.year(2026).previous() == Period.year(2025)


def test_shifted_forward_keeps_february_whole():
    assert Period.of_months(Month(2026, 1)).shifted(1) == Period(
        date(2026, 2, 1), date(2026, 2, 28)
    )


def test_previous_of_loose_days_moves_by_days():
    period = Period(date(2026, 11, 10), date(2026, 11, 19))

    assert period.previous() == Period(date(2026, 10, 31), date(2026, 11, 9))
    assert period.days == 10


@pytest.mark.parametrize(
    ("period", "label"),
    [
        (Period.of_months(Month(2026, 11)), "Noviembre 2026"),
        (Period.of_months(Month(2026, 9), Month(2026, 11)), "Sep – Nov 2026"),
        (Period.of_months(Month(2025, 12), Month(2026, 11)), "Dic 2025 – Nov 2026"),
        (Period.year(2026), "2026"),
        (Period(date(2026, 11, 10), date(2026, 11, 19)), "10/11/2026 – 19/11/2026"),
    ],
)
def test_label(period, label):
    assert period.label() == label


def test_contains_is_inclusive():
    period = Period.of_months(Month(2026, 11))

    assert period.contains(date(2026, 11, 1))
    assert period.contains(date(2026, 11, 30))
    assert not period.contains(date(2026, 12, 1))
