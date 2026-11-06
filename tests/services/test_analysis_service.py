from datetime import date
from decimal import Decimal

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.analysis_service import Metric
from nodus.services.transaction_service import TransferDraft

EXPENSE, INCOME = TransactionType.EXPENSE, TransactionType.INCOME
SEP_NOV = Period.of_months(Month(2026, 9), Month(2026, 11))


def spend(services, account, amount, on, **overrides):
    services.transactions.create(expense_draft(services, account.id, amount, on, **overrides))


def earn(services, account, amount, on, **overrides):
    services.transactions.create(income_draft(services, account.id, amount, on, **overrides))


@pytest.fixture
def history(services, pesos, dollars):
    """Three months of movements, a transfer, a dollar expense with and without a rate,
    and one month in the previous period."""
    services.exchange_rates.set_rate(date(2026, 10, 1), Decimal("1000"))
    earn(services, pesos, ars("1000"), date(2026, 9, 1))
    spend(services, pesos, ars("300"), date(2026, 9, 5), payee_name="Coto")
    earn(services, pesos, ars("1000"), date(2026, 10, 1))
    spend(services, pesos, ars("200"), date(2026, 10, 5), payee_name="Coto")
    spend(services, dollars, usd("1"), date(2026, 10, 6), payee_name="Día")  # $ 1.000
    spend(services, dollars, usd("2"), date(2026, 9, 20))  # before any rate
    spend(
        services, pesos, ars("100"), date(2026, 11, 2),
        category_id=category_id(services, "Servicios", EXPENSE),
    )  # fmt: skip
    spend(services, pesos, ars("400"), date(2026, 6, 10))  # previous period
    services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("5000"), date(2026, 10, 9), amount_in=usd("5"))
    )


class TestTrends:
    def test_expenses_month_by_month_without_transfers(self, services, history):
        trends = services.analysis.trends(SEP_NOV, Metric.EXPENSES)

        assert [m.month for m in trends.months] == SEP_NOV.months()
        assert [m.total for m in trends.months] == [ars("300"), ars("1200"), ars("100")]
        assert trends.total == ars("1600")
        assert trends.unconverted == 1

    def test_against_the_previous_period_of_the_same_length(self, services, history):
        trends = services.analysis.trends(SEP_NOV, Metric.EXPENSES)

        assert trends.previous_total == ars("400")
        assert trends.change == pytest.approx(3.0)

    def test_average_per_month(self, services, history):
        assert services.analysis.trends(SEP_NOV, Metric.EXPENSES).average == ars("533.33")

    def test_categories_and_payees_largest_first(self, services, history):
        trends = services.analysis.trends(SEP_NOV, Metric.EXPENSES)

        assert [(t.category.name, t.total) for t in trends.categories] == [
            ("Supermercado y comida", ars("1500")),
            ("Servicios", ars("100")),
        ]
        assert [(p.payee.name if p.payee else None, p.total, p.count) for p in trends.payees] == [
            ("Día", ars("1000"), 1),
            ("Coto", ars("500"), 2),
            (None, ars("100"), 1),
        ]

    def test_subcategories_add_up_in_their_parent(self, services, pesos):
        vivienda = category_id(services, "Vivienda", EXPENSE)
        alquiler = services.categories.create("Alquiler", EXPENSE, "#e67e22", parent_id=vivienda)
        spend(services, pesos, ars("700"), date(2026, 10, 3), category_id=alquiler.id)

        trends = services.analysis.trends(SEP_NOV, Metric.EXPENSES)

        assert [(t.category.id, t.total) for t in trends.categories] == [(vivienda, ars("700"))]
        assert trends.months[1].by_category[0].category.id == vivienda

    def test_income(self, services, history):
        trends = services.analysis.trends(SEP_NOV, Metric.INCOME)

        assert [m.total for m in trends.months] == [ars("1000"), ars("1000"), ars("0")]
        assert trends.categories[0].category.name == "Sueldo"

    def test_savings_can_be_negative_and_has_no_breakdown(self, services, history):
        trends = services.analysis.trends(SEP_NOV, Metric.SAVINGS)

        assert [m.total for m in trends.months] == [ars("700"), ars("-200"), ars("-100")]
        assert trends.total == ars("400")
        assert trends.previous_total == ars("-400")
        assert (trends.categories, trends.payees) == ([], [])

    def test_empty_period(self, services):
        trends = services.analysis.trends(SEP_NOV, Metric.EXPENSES)

        assert trends.total == ars("0")
        assert trends.change is None
        assert trends.categories == []


class TestCashFlow:
    def test_months_totals_and_savings_rate(self, services, history):
        report = services.analysis.cash_flow(SEP_NOV)

        assert [(m.income, m.expenses) for m in report.months] == [
            (ars("1000"), ars("300")),
            (ars("1000"), ars("1200")),
            (ars("0"), ars("100")),
        ]
        assert report.current.savings == ars("400")
        assert report.current.savings_rate == pytest.approx(0.2)
        assert report.months[2].savings_rate is None
        assert report.previous.expenses == ars("400")
        assert report.previous.savings_rate is None
        assert report.unconverted == 1

    def test_single_month_is_not_widened(self, services, history):
        report = services.analysis.cash_flow(Period.of_months(Month(2026, 10)))

        assert [m.month for m in report.months] == [Month(2026, 10)]
