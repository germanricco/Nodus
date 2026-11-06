from datetime import date
from decimal import Decimal

import pytest
from factories import TODAY, ars, category_id, expense_draft, income_draft, usd

from nodus.models.budget import BudgetState
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.services.errors import ValidationError

NOVEMBER = Month.of(TODAY)


def food(services) -> int:
    return category_id(services, "Supermercado y comida", TransactionType.EXPENSE)


def spend(services, account_id, amount, on=TODAY, **overrides):
    services.transactions.create(expense_draft(services, account_id, amount, on, **overrides))


def limit_in(services, month, category):
    return services.budgets.limits_on(month).get(category)


def test_a_limit_applies_from_its_month_until_it_changes(services):
    category = food(services)
    services.budgets.set_limit(category, Month(2026, 8), ars("300000"))
    services.budgets.set_limit(category, Month(2026, 9), ars("400000"))
    services.budgets.remove(category, Month(2026, 10))

    assert limit_in(services, Month(2026, 7), category) is None
    assert limit_in(services, Month(2026, 8), category) == ars("300000")
    assert limit_in(services, Month(2026, 9), category) == ars("400000")
    assert limit_in(services, Month(2026, 10), category) is None
    assert limit_in(services, Month(2026, 12), category) is None


def test_setting_the_same_month_twice_replaces_it(services):
    category = food(services)
    services.budgets.set_limit(category, NOVEMBER, ars("100"))
    services.budgets.set_limit(category, NOVEMBER, ars("200"))

    assert limit_in(services, NOVEMBER, category) == ars("200")


@pytest.mark.parametrize(
    ("name", "kind", "amount", "message"),
    [
        ("Sueldo", TransactionType.INCOME, ars("100"), "gasto"),
        ("Supermercado y comida", TransactionType.EXPENSE, usd("100"), "pesos"),
        ("Supermercado y comida", TransactionType.EXPENSE, ars("0"), "mayor que cero"),
    ],
)
def test_set_limit_validates(services, name, kind, amount, message):
    with pytest.raises(ValidationError, match=message):
        services.budgets.set_limit(category_id(services, name, kind), NOVEMBER, amount)


def test_subcategories_cannot_have_their_own_budget(services):
    sub = services.categories.create("Verdulería", TransactionType.EXPENSE, "#000", food(services))
    with pytest.raises(ValidationError, match="principal"):
        services.budgets.set_limit(sub.id, NOVEMBER, ars("100"))


def test_month_counts_expenses_of_the_category_and_its_subcategories(services, pesos):
    category = food(services)
    sub = services.categories.create("Verdulería", TransactionType.EXPENSE, "#000", category)
    services.budgets.set_limit(category, NOVEMBER, ars("1000"))
    spend(services, pesos.id, ars("300"))
    spend(services, pesos.id, ars("200"), category_id=sub.id)
    spend(services, pesos.id, ars("999"), on=date(2026, 10, 31))  # another month
    services.transactions.create(income_draft(services, pesos.id, ars("5000")))

    (budget,) = services.budgets.month_budgets(NOVEMBER, TODAY).budgets

    assert budget.spent == ars("500")
    assert budget.remaining == ars("500")


def test_month_converts_dollar_expenses_and_counts_the_unconvertible(services, pesos, dollars):
    category = food(services)
    services.budgets.set_limit(category, NOVEMBER, ars("100000"))
    spend(services, dollars.id, usd("10"))
    month = services.budgets.month_budgets(NOVEMBER, TODAY)
    assert month.unconverted == 1
    assert month.budgets[0].spent == ars("0")

    services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1000"))

    assert services.budgets.month_budgets(NOVEMBER, TODAY).budgets[0].spent == ars("10000")


def test_month_orders_by_use_and_lists_spending_without_budget(services, pesos):
    leisure = category_id(services, "Ocio", TransactionType.EXPENSE)
    transport = category_id(services, "Transporte", TransactionType.EXPENSE)
    services.budgets.set_limit(food(services), NOVEMBER, ars("1000"))
    services.budgets.set_limit(leisure, NOVEMBER, ars("100"))
    spend(services, pesos.id, ars("100"))
    spend(services, pesos.id, ars("90"), category_id=leisure)
    spend(services, pesos.id, ars("50"), category_id=transport)

    month = services.budgets.month_budgets(NOVEMBER, TODAY)

    assert [b.category.name for b in month.budgets] == ["Ocio", "Supermercado y comida"]
    assert [t.category.name for t in month.unbudgeted] == ["Transporte"]
    assert (month.limit, month.spent, month.remaining) == (ars("1100"), ars("190"), ars("910"))


def test_over_limit_looks_only_at_the_current_month(services, pesos):
    category = food(services)
    services.budgets.set_limit(category, Month(2026, 10), ars("100"))
    spend(services, pesos.id, ars("500"), on=date(2026, 10, 15))
    assert services.budgets.over_limit(TODAY) == []

    spend(services, pesos.id, ars("150"))

    (budget,) = services.budgets.over_limit(TODAY)
    assert budget.state is BudgetState.OVER


def test_suggestion_is_the_average_of_the_last_three_months(services, pesos):
    category = food(services)
    assert services.budgets.suggestion(category, NOVEMBER) is None

    for month, amount in ((8, "301000"), (9, "400000"), (10, "350000")):
        spend(services, pesos.id, ars(amount), on=date(2026, month, 10))
    spend(services, pesos.id, ars("900000"), on=date(2026, 7, 10))  # too old to count

    assert services.budgets.suggestion(category, NOVEMBER) == ars("350000")


def test_deleting_a_category_deletes_its_limits(services):
    category = services.categories.create("Mascotas", TransactionType.EXPENSE, "#000")
    services.budgets.set_limit(category.id, NOVEMBER, ars("100"))

    services.categories.delete(category.id)

    assert services.budgets.limits_on(NOVEMBER) == {}
