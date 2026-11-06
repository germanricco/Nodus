from datetime import date
from decimal import Decimal

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.dashboard_service import relative_change
from nodus.services.transaction_service import TransferDraft

NOVEMBER = Period.of_months(Month(2026, 11))
EXPENSE = TransactionType.EXPENSE


def test_month_totals_exclude_transfers_and_other_months(services, pesos, dollars):
    services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1000"))
    services.transactions.create(income_draft(services, pesos.id, ars("500000")))
    services.transactions.create(expense_draft(services, pesos.id, ars("120000")))
    services.transactions.create(expense_draft(services, pesos.id, ars("1"), on=date(2026, 10, 31)))
    services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("100000"), date(2026, 11, 2), amount_in=usd("100"))
    )

    summary = services.dashboard.summary(NOVEMBER)

    assert summary.income == ars("500000")
    assert summary.expenses == ars("120000")
    assert summary.savings == ars("380000")
    assert summary.unconverted == 0


def test_expenses_grouped_by_top_level_category_largest_first(services, pesos):
    vivienda = category_id(services, "Vivienda", EXPENSE)
    alquiler = services.categories.create("Alquiler", EXPENSE, "#000000", parent_id=vivienda)
    services.transactions.create(expense_draft(services, pesos.id, ars("1000")))
    services.transactions.create(
        expense_draft(services, pesos.id, ars("700"), category_id=alquiler.id)
    )
    services.transactions.create(
        expense_draft(services, pesos.id, ars("600"), category_id=vivienda)
    )

    summary = services.dashboard.summary(NOVEMBER)

    assert [(t.category.name, t.total) for t in summary.expenses_by_category] == [
        ("Vivienda", ars("1300")),
        ("Supermercado y comida", ars("1000")),
    ]


def test_dollar_movements_convert_at_their_day_or_are_reported(services, dollars):
    services.transactions.create(
        expense_draft(services, dollars.id, usd("10"), on=date(2026, 11, 1))
    )
    services.exchange_rates.set_rate(date(2026, 11, 3), Decimal("1200"))
    services.transactions.create(
        expense_draft(services, dollars.id, usd("20"), on=date(2026, 11, 4))
    )

    summary = services.dashboard.summary(NOVEMBER)

    assert summary.expenses == ars("24000")
    assert summary.unconverted == 1


def test_relative_change():
    assert relative_change(ars("150"), ars("100")) == 0.5
    assert relative_change(ars("-50"), ars("-100")) == 0.5  # less negative is better
    assert relative_change(ars("10"), ars("0")) is None


def test_comparison_with_the_previous_period(services, pesos):
    transporte = category_id(services, "Transporte", EXPENSE)
    services.transactions.create(expense_draft(services, pesos.id, ars("1000")))
    services.transactions.create(
        expense_draft(services, pesos.id, ars("800"), on=date(2026, 10, 10))
    )
    services.transactions.create(
        expense_draft(services, pesos.id, ars("300"), category_id=transporte)
    )
    services.transactions.create(income_draft(services, pesos.id, ars("5000")))
    services.transactions.create(
        income_draft(services, pesos.id, ars("4000"), on=date(2026, 10, 1))
    )

    comparison = services.dashboard.comparison(NOVEMBER)

    assert comparison.previous.period == Period.of_months(Month(2026, 10))
    changes = [(c.category.name, c.current, c.previous, c.change) for c in comparison.categories]
    assert changes == [
        ("Supermercado y comida", ars("1000"), ars("800"), 0.25),
        ("Transporte", ars("300"), ars("0"), None),
    ]
    assert comparison.expenses_change == pytest.approx(0.625)
    assert comparison.savings_change == pytest.approx((3700 - 3200) / 3200)


def test_monthly_flow_of_one_month_shows_the_six_leading_to_it(services, pesos):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("100"), on=date(2026, 6, 30))
    )
    services.transactions.create(income_draft(services, pesos.id, ars("900")))

    flow = services.dashboard.monthly_flow(NOVEMBER)

    assert [f.month for f in flow] == [Month(2026, m) for m in range(6, 12)]
    assert (flow[0].expenses, flow[0].savings) == (ars("100"), ars("-100"))
    assert (flow[-1].income, flow[-1].savings) == (ars("900"), ars("900"))


def test_monthly_flow_of_several_months_uses_their_months(services, pesos):
    period = Period.of_months(Month(2026, 9), Month(2026, 11))

    flow = services.dashboard.monthly_flow(period)

    assert [f.month for f in flow] == period.months()
    assert all(f.income.is_zero and f.expenses.is_zero for f in flow)
