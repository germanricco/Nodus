from datetime import date, datetime

import pytest
from factories import TODAY

from nodus.models.period import (
    Month,
    Period,
    QuickPeriod,
    format_date,
    format_day_month,
    format_month,
    format_month_in_sentence,
    format_time,
    qt_date_format,
)


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


class TestMonthsSince:
    """The months with a history: what a monthly average divides by."""

    YEAR = Period.year(2026)

    def test_from_the_month_of_the_first_movement_through_the_current_one(self):
        months = self.YEAR.months_since(date(2026, 9, 28), date(2026, 11, 5))

        assert months == [Month(2026, 9), Month(2026, 10), Month(2026, 11)]

    def test_one_month_of_use_is_one_month(self):
        assert self.YEAR.months_since(date(2026, 11, 6), date(2026, 11, 9)) == [Month(2026, 11)]

    def test_a_history_older_than_the_period_counts_all_its_months_until_today(self):
        months = self.YEAR.months_since(date(2020, 1, 1), date(2026, 3, 31))

        assert months == [Month(2026, 1), Month(2026, 2), Month(2026, 3)]

    def test_a_period_already_over_counts_whole(self):
        assert len(self.YEAR.months_since(date(2020, 1, 1), date(2027, 6, 1))) == 12

    def test_nothing_when_the_history_starts_after_the_period_or_it_has_not_come(self):
        assert self.YEAR.months_since(date(2027, 2, 1), date(2027, 3, 1)) == []
        assert self.YEAR.months_since(date(2020, 1, 1), date(2025, 12, 31)) == []


def test_contains_is_inclusive():
    period = Period.of_months(Month(2026, 11))

    assert period.contains(date(2026, 11, 1))
    assert period.contains(date(2026, 11, 30))
    assert not period.contains(date(2026, 12, 1))


def test_months_to_counts_whole_calendar_months():
    assert Month(2026, 11).months_to(Month(2027, 3)) == 4
    assert Month(2026, 11).months_to(Month(2026, 11)) == 0
    assert Month(2027, 3).months_to(Month(2026, 11)) == -4


def test_in_english_dates_go_month_first_and_months_are_in_english(english):
    day = date(2026, 11, 5)

    assert format_date(day) == "11/05/2026"
    assert format_day_month(day) == "11/05"
    assert format_time(datetime(2026, 11, 5, 9, 30)) == "9:30 AM"
    assert format_time(datetime(2026, 11, 5, 0, 5)) == "12:05 AM"
    assert format_time(datetime(2026, 11, 5, 21, 30)) == "9:30 PM"
    assert qt_date_format() == "MM/dd/yyyy"
    assert format_month(Month(2026, 11)) == "November 2026"
    assert format_month_in_sentence(Month(2027, 10)) == "October 2027"
    assert Month(2026, 9).short_name == "Sep"


def test_in_spanish_months_inside_a_sentence_are_lowercase_and_hours_go_to_24():
    assert format_month(Month(2026, 11)) == "Noviembre 2026"
    assert format_month_in_sentence(Month(2027, 10)) == "octubre de 2027"
    assert format_time(datetime(2026, 11, 5, 9, 30)) == "09:30"
    assert qt_date_format() == "dd/MM/yyyy"


def test_in_english_the_ready_made_periods_are_named_in_english(english):
    assert [quick.label for quick in QuickPeriod][:2] == ["This month", "Last 3 months"]


class TestFromMonth:
    YEAR = Period.of_months(Month(2025, 12), Month(2026, 11))

    def test_drops_the_months_before_the_first_movement(self):
        assert self.YEAR.from_month(Month(2026, 6)).months()[0] == Month(2026, 6)
        assert self.YEAR.from_month(Month(2026, 6)).last_month == Month(2026, 11)

    def test_without_movements_or_with_them_since_before_it_stays_whole(self):
        assert self.YEAR.from_month(None) == self.YEAR
        assert self.YEAR.from_month(Month(2020, 1)) == self.YEAR

    def test_a_period_before_the_first_movement_stays_whole_to_say_so(self):
        assert self.YEAR.from_month(Month(2027, 3)) == self.YEAR
