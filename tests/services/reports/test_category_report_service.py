from datetime import date
from decimal import Decimal

import pytest
from factories import TODAY, ars, category_id, expense_draft, income_draft, usd

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType

EXPENSE, INCOME = TransactionType.EXPENSE, TransactionType.INCOME
NOVEMBER = Period.of_months(Month(2026, 11))


def spend(services, account, amount, category, on=TODAY):
    services.transactions.create(
        expense_draft(
            services, account.id, amount, on, category_id=category_id(services, category, EXPENSE)
        )
    )


def section(report, kind):
    return next(s for s in report.sections if s.kind is kind)


def by_name(figures):
    return {f.category.name: f for f in figures}


@pytest.fixture
def rent(services):
    """«Alquiler», a subcategory of «Vivienda»."""
    vivienda = category_id(services, "Vivienda", EXPENSE)
    services.categories.create("Alquiler", EXPENSE, "#ff0000", parent_id=vivienda)


def test_each_category_adds_up_its_movements_largest_first(services, pesos, dollars):
    services.exchange_rates.set_rate(TODAY, Decimal("1000"))
    spend(services, pesos, ars("300"), "Supermercado y comida")
    spend(services, dollars, usd("1"), "Ocio")  # $ 1.000
    spend(services, pesos, ars("100"), "Supermercado y comida")
    services.transactions.create(income_draft(services, pesos.id, ars("5000")))

    report = services.category_report.report(NOVEMBER)

    expenses = section(report, EXPENSE)
    assert expenses.total == ars("1400")
    names = [f.category.name for f in expenses.categories]
    assert names[:2] == ["Ocio", "Supermercado y comida"]
    food = by_name(expenses.categories)["Supermercado y comida"]
    assert (food.total, food.count) == (ars("400"), 2)
    assert food.share == pytest.approx(400 / 1400)
    assert section(report, INCOME).total == ars("5000")


def test_categories_without_movements_go_last_with_no_share(services, pesos):
    spend(services, pesos, ars("100"), "Ocio")

    expenses = section(services.category_report.report(NOVEMBER), EXPENSE)

    assert expenses.categories[0].category.name == "Ocio"
    quiet = expenses.categories[1:]
    assert all(f.count == 0 and f.total.is_zero for f in quiet)
    assert quiet[-1].category.is_system  # «Otros» stays at the end
    assert section(services.category_report.report(NOVEMBER), INCOME).categories[0].share is None


def test_a_parent_adds_up_its_subcategories(services, pesos, rent):
    spend(services, pesos, ars("400"), "Alquiler")
    spend(services, pesos, ars("100"), "Vivienda")

    expenses = section(services.category_report.report(NOVEMBER), EXPENSE)

    housing = by_name(expenses.categories)["Vivienda"]
    assert (housing.total, housing.count) == (ars("500"), 2)
    assert [(c.category.name, c.total) for c in housing.children] == [("Alquiler", ars("400"))]
    assert housing.children[0].share == pytest.approx(0.8)


def test_only_the_period_counts(services, pesos):
    spend(services, pesos, ars("100"), "Ocio", on=date(2026, 10, 31))

    expenses = section(services.category_report.report(NOVEMBER), EXPENSE)

    assert expenses.total.is_zero


def test_expenses_match_the_dashboard_ring(services, pesos, dollars, rent):
    """Inicio and Categorías show the same spending per category: one way of counting."""
    services.exchange_rates.set_rate(TODAY, Decimal("1000"))
    spend(services, pesos, ars("400"), "Alquiler")
    spend(services, pesos, ars("100"), "Vivienda")
    spend(services, dollars, usd("2"), "Ocio")

    ring = services.dashboard.summary(NOVEMBER).expenses_by_category
    listed = section(services.category_report.report(NOVEMBER), EXPENSE).categories

    assert [(t.category.id, t.total) for t in ring] == [
        (f.category.id, f.total) for f in listed if f.count
    ]
