from datetime import date
from decimal import Decimal

from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
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
