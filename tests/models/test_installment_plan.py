"""The calendar of a purchase in installments: what it should do and the edges that break it."""

from datetime import date

import pytest
from factories import ars

from nodus.models.installment_plan import Installment, InstallmentPlan
from nodus.models.money import Money
from nodus.models.period import Month


def plan(total="75000", count=6, first=date(2026, 11, 10), settled_on=None) -> InstallmentPlan:
    return InstallmentPlan(None, count, ars(total), first, settled_on)


class TestAmounts:
    def test_an_even_total_splits_in_equal_installments(self):
        assert plan().amounts() == [ars("12500")] * 6

    def test_the_cents_left_over_go_to_the_first_installment(self):
        assert plan("100", 3).amounts() == [ars("33.34"), ars("33.33"), ars("33.33")]

    @pytest.mark.parametrize(
        ("cents", "count"),
        [
            (cents, count)
            for cents in (2, 3, 7, 99, 100, 101, 7_500_000, 999_999_999)
            for count in (2, 3, 6, 7, 12, 18, 72)
            if cents >= count  # less than a cent each is rejected, see TestLimits
        ],
    )
    def test_any_split_adds_up_and_differs_by_less_than_a_cent_per_installment(self, cents, count):
        amounts = InstallmentPlan(None, count, Money(cents, ars("0").currency), date.today())
        parts = [m.cents for m in amounts.amounts()]

        assert sum(parts) == cents
        assert len(parts) == count
        assert max(parts[1:]) == min(parts[1:])  # every one after the first is equal
        assert 0 <= parts[0] - parts[1] < count  # the first carries only the remainder

    def test_per_installment_amount_gives_the_total(self):
        by_installment = InstallmentPlan.from_installment_amount(
            ars("12500"), 6, date(2026, 11, 10)
        )

        assert by_installment.total == ars("75000")
        assert by_installment.amounts() == [ars("12500")] * 6


class TestLimits:
    @pytest.mark.parametrize("count", [-1, 0, 1, 73])
    def test_out_of_range_counts_are_rejected(self, count):
        with pytest.raises(ValueError):
            plan(count=count)

    @pytest.mark.parametrize(("total", "count"), [("0.05", 6), ("0.01", 2), ("0", 2)])
    def test_less_than_a_cent_per_installment_is_rejected(self, total, count):
        with pytest.raises(ValueError):
            plan(total, count)

    def test_paying_off_before_the_first_installment_is_rejected(self):
        with pytest.raises(ValueError):
            plan(settled_on=date(2026, 11, 9))

    @pytest.mark.parametrize(("number", "count"), [(0, 6), (7, 6), (-1, 6)])
    def test_an_installment_out_of_its_purchase_is_rejected(self, number, count):
        with pytest.raises(ValueError):
            Installment(1, number, count)

    def test_installment_label(self):
        assert Installment(1, 3, 6).label == "3/6"


class TestDates:
    def test_monthly_on_the_same_day(self):
        assert plan(count=3).due_dates() == [
            date(2026, 11, 10), date(2026, 12, 10), date(2027, 1, 10),
        ]  # fmt: skip

    def test_the_31st_falls_on_the_last_day_and_comes_back(self):
        days = plan(count=4, first=date(2027, 1, 31)).due_dates()

        assert days == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]

    def test_leap_years(self):
        days = plan(count=13, first=date(2028, 2, 29)).due_dates()

        assert days[1] == date(2028, 3, 29)
        assert days[12] == date(2029, 2, 28)

    def test_72_installments_cross_six_years_strictly_in_order(self):
        days = plan("72000", 72, date(2026, 12, 31)).due_dates()

        assert days[-1] == Month(2032, 11).end
        assert all(a < b for a, b in zip(days, days[1:], strict=False))

    def test_the_day_of_month_helper_matches_short_months(self):
        assert Month(2027, 2).day(31) == date(2027, 2, 28)
        assert Month(2027, 3).day(15) == date(2027, 3, 15)


class TestProgress:
    def test_todays_installment_has_already_come_off(self):
        assert plan().due_count(date(2026, 11, 9)) == 0
        assert plan().due_count(date(2026, 11, 10)) == 1
        assert plan().due_count(date(2026, 12, 9)) == 1

    def test_remaining_is_what_comes_after_today(self):
        assert plan().remaining(date(2026, 11, 10)) == ars("62500")
        assert plan().remaining(date(2027, 4, 10)) == ars("0")

    def test_remaining_keeps_the_first_installments_remainder(self):
        three = plan("100", 3)

        assert three.remaining(date(2026, 11, 9)) == ars("100")
        assert three.remaining(date(2026, 11, 10)) == ars("66.66")


class TestPayingOff:
    def test_the_installments_after_the_day_fall_on_it(self):
        settled = plan(count=4, settled_on=date(2026, 12, 20)).due_dates()

        assert settled == [date(2026, 11, 10), date(2026, 12, 10)] + [date(2026, 12, 20)] * 2

    def test_on_the_day_of_an_installment(self):
        settled = plan(count=3, settled_on=date(2026, 12, 10)).due_dates()

        assert settled == [date(2026, 11, 10), date(2026, 12, 10), date(2026, 12, 10)]

    def test_after_the_last_one_changes_nothing(self):
        assert plan(count=3, settled_on=date(2030, 1, 1)).due_dates() == plan(count=3).due_dates()

    def test_clearing_it_brings_the_calendar_back(self):
        settled = plan(settled_on=date(2026, 12, 20))
        cleared = InstallmentPlan(None, 6, settled.total, settled.first_due_on, None)

        assert cleared.due_dates() == plan().due_dates()
