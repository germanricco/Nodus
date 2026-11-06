"""Refunds: an income linked to the expense it pays back counts as less spending."""

from datetime import date
from decimal import Decimal

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.analysis_service import Metric
from nodus.services.errors import ValidationError
from nodus.services.transaction_service import TransferDraft

INCOME = TransactionType.INCOME
EXPENSE = TransactionType.EXPENSE
OCTOBER, NOVEMBER = Month(2026, 10), Month(2026, 11)


def refund_draft(services, account_id, amount, expense, on=date(2026, 11, 3), **overrides):
    """An income in "Reembolsos" that pays back ``expense``."""
    return income_draft(
        services, account_id, amount, on,
        category_id=category_id(services, "Reembolsos", INCOME), refund_of_id=expense.id,
        **overrides,
    )  # fmt: skip


@pytest.fixture
def purchase(services, pesos):
    """A $ 1.000 grocery purchase in October."""
    return services.transactions.create(
        expense_draft(services, pesos.id, ars("1000"), date(2026, 10, 20))
    )


def summary(services, month):
    return services.dashboard.summary(Period.of_months(month))


def test_refund_lowers_spending_in_the_month_it_comes_back(services, pesos, purchase):
    services.transactions.create(refund_draft(services, pesos.id, ars("400"), purchase))

    october, november = summary(services, OCTOBER), summary(services, NOVEMBER)

    assert october.expenses == ars("1000")  # past months stay as they were
    assert november.income == ars("0")  # a linked refund is not income
    assert november.expenses == ars("-400")
    assert november.expenses_by_category == []  # a category does not go below zero


def test_refund_nets_against_the_original_category(services, pesos, purchase):
    services.transactions.create(expense_draft(services, pesos.id, ars("700"), date(2026, 11, 1)))
    services.transactions.create(refund_draft(services, pesos.id, ars("400"), purchase))

    november = summary(services, NOVEMBER)

    assert november.expenses == ars("300")
    ((groceries),) = november.expenses_by_category
    assert (groceries.category.name, groceries.total) == ("Supermercado y comida", ars("300"))


def test_refunds_cannot_exceed_the_expense(services, pesos, purchase):
    first = services.transactions.create(refund_draft(services, pesos.id, ars("600"), purchase))

    with pytest.raises(ValidationError, match=r"\$ 400,00"):
        services.transactions.create(refund_draft(services, pesos.id, ars("500"), purchase))
    # Editing a refund does not count its own amount against it.
    services.transactions.update(first.id, refund_draft(services, pesos.id, ars("1000"), purchase))

    refund_summary = services.transactions.refund_summary(purchase.id)
    assert refund_summary.refunded == ars("1000")
    assert refund_summary.remaining == ars("0")


def test_refund_in_another_currency_has_no_cap(services, pesos, dollars, purchase):
    services.exchange_rates.set_rate(date(2026, 11, 3), Decimal("1000"))

    services.transactions.create(refund_draft(services, dollars.id, usd("2"), purchase))

    assert summary(services, NOVEMBER).expenses == ars("-2000")
    assert services.transactions.refund_summary(purchase.id).remaining == ars("1000")


def test_only_an_expense_can_be_refunded(services, pesos, dollars):
    income = services.transactions.create(income_draft(services, pesos.id, ars("100")))
    transfer = services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("1000"), date(2026, 11, 1), amount_in=usd("1"))
    )

    for target in (income, transfer.outgoing):
        with pytest.raises(ValidationError, match="devolver un gasto"):
            services.transactions.create(refund_draft(services, pesos.id, ars("10"), target))


def test_expense_cannot_shrink_below_its_refunds(services, pesos, purchase):
    services.transactions.create(refund_draft(services, pesos.id, ars("600"), purchase))

    with pytest.raises(ValidationError, match="no puede ser menor"):
        services.transactions.update(
            purchase.id, expense_draft(services, pesos.id, ars("500"), date(2026, 10, 20))
        )


def test_deleting_the_expense_turns_refunds_into_income(services, pesos, purchase):
    refund = services.transactions.create(refund_draft(services, pesos.id, ars("400"), purchase))

    services.transactions.delete(purchase.id)

    assert services.transactions.get(refund.id).refund_of_id is None
    assert summary(services, NOVEMBER).income == ars("400")


def test_changing_the_type_breaks_the_link(services, pesos, purchase):
    refund = services.transactions.create(refund_draft(services, pesos.id, ars("400"), purchase))

    # The expense turned into income frees its refunds...
    services.transactions.update(
        purchase.id, income_draft(services, pesos.id, ars("1000"), date(2026, 10, 20))
    )
    assert services.transactions.get(refund.id).refund_of_id is None

    # ...and a refund turned into an expense loses its link.
    other = services.transactions.create(
        expense_draft(services, pesos.id, ars("50"), date(2026, 10, 1))
    )
    services.transactions.update(refund.id, refund_draft(services, pesos.id, ars("40"), other))
    services.transactions.update(
        refund.id, expense_draft(services, pesos.id, ars("40"), refund_of_id=other.id)
    )
    assert services.transactions.get(refund.id).refund_of_id is None


def test_budgets_and_trends_see_the_net_spending(services, pesos, purchase):
    groceries = category_id(services, "Supermercado y comida", EXPENSE)
    services.budgets.set_limit(groceries, NOVEMBER, ars("5000"))
    services.transactions.create(expense_draft(services, pesos.id, ars("700"), date(2026, 11, 1)))
    services.transactions.create(refund_draft(services, pesos.id, ars("400"), purchase))

    (budget,) = services.budgets.month_budgets(NOVEMBER, date(2026, 11, 5)).budgets
    trends = services.analysis.trends(Period.of_months(OCTOBER, NOVEMBER), Metric.EXPENSES)
    income = services.analysis.trends(Period.of_months(OCTOBER, NOVEMBER), Metric.INCOME)

    assert budget.spent == ars("300")
    assert [month.total for month in trends.months] == [ars("1000"), ars("300")]
    assert trends.total == ars("1300")
    assert income.total == ars("0")
