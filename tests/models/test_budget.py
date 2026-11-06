from datetime import date

import pytest
from factories import ars

from nodus.models.budget import Budget, BudgetState, month_elapsed, used_percent_label
from nodus.models.category import Category
from nodus.models.period import Month
from nodus.models.transaction import TransactionType

FOOD = Category(1, "Supermercado y comida", TransactionType.EXPENSE, "#e74c3c")


def budget(spent: str, elapsed: float, limit: str = "1000") -> Budget:
    return Budget(FOOD, ars(limit), ars(spent), elapsed)


@pytest.mark.parametrize(
    ("month", "elapsed"),
    [(Month(2026, 10), 1.0), (Month(2026, 12), 0.0), (Month(2026, 11), 10 / 30)],
)
def test_month_elapsed(month, elapsed):
    assert month_elapsed(month, date(2026, 11, 10)) == pytest.approx(elapsed)


@pytest.mark.parametrize(
    ("spent", "elapsed", "state"),
    [
        ("1000", 1.0, BudgetState.ON_TRACK),  # right at the limit is not over
        ("1000", 0.5, BudgetState.AHEAD),
        ("1000.01", 1.0, BudgetState.OVER),
        ("700", 0.1, BudgetState.ON_TRACK),  # a rent paid on the 1st stays on track up to 70 %
        ("710", 0.1, BudgetState.AHEAD),
        ("800", 0.9, BudgetState.ON_TRACK),  # late in the month, the pace allows more
        ("950", 0.9, BudgetState.AHEAD),
    ],
)
def test_state_follows_the_pace_of_the_month(spent, elapsed, state):
    assert budget(spent, elapsed).state is state


def test_remaining_goes_negative_over_the_limit():
    assert budget("1200", 1.0).remaining == ars("-200")
    assert budget("1200", 1.0).used == pytest.approx(1.2)


@pytest.mark.parametrize(
    ("used", "label"),
    [
        (0, "0 %"),
        (0.004, "<1 %"),
        (0.654, "65 %"),
        (0.998, "99 %"),
        (1.0, "100 %"),
        (1.25, "125 %"),
    ],
)
def test_used_percent_label(used, label):
    assert used_percent_label(used) == label
