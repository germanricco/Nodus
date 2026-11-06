"""What the movements of a filter add up to, for the foot of the transactions list."""

from datetime import date
from decimal import Decimal

from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.transaction import TransactionType
from nodus.services.transaction_service import TransferDraft

NOVEMBER = TransactionFilter(start=date(2026, 11, 1), end=date(2026, 11, 30))


def test_adds_up_income_and_expenses_in_pesos(services, pesos, dollars):
    services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1000"))
    services.transactions.create(expense_draft(services, pesos.id, ars("500"), date(2026, 11, 2)))
    services.transactions.create(expense_draft(services, dollars.id, usd("2"), date(2026, 11, 3)))
    services.transactions.create(income_draft(services, pesos.id, ars("9000"), date(2026, 11, 4)))
    services.transactions.create(
        expense_draft(services, pesos.id, ars("1"), date(2026, 10, 31))
    )  # outside the filter

    totals = services.dashboard.totals(NOVEMBER)

    assert (totals.income, totals.expenses, totals.net) == (ars("9000"), ars("2500"), ars("6500"))
    assert totals.unconverted == 0


def test_counts_dollars_without_a_rate_apart(services, dollars):
    services.transactions.create(expense_draft(services, dollars.id, usd("2"), date(2026, 11, 3)))

    totals = services.dashboard.totals(NOVEMBER)

    assert (totals.expenses, totals.unconverted) == (ars("0"), 1)


def test_follows_the_filter_and_nets_refunds(services, pesos):
    shoes = services.transactions.create(
        expense_draft(services, pesos.id, ars("1000"), date(2026, 11, 2), tag_names=("Viaje",))
    )
    services.transactions.create(
        income_draft(
            services, pesos.id, ars("300"), date(2026, 11, 5), tag_names=("Viaje",),
            category_id=category_id(services, "Reembolsos", TransactionType.INCOME),
            refund_of_id=shoes.id,
        )
    )  # fmt: skip
    services.transactions.create(expense_draft(services, pesos.id, ars("50"), date(2026, 11, 2)))
    viaje = services.tags.find("Viaje").id

    totals = services.dashboard.totals(TransactionFilter(tag_id=viaje))

    assert (totals.income, totals.expenses) == (ars("0"), ars("700"))


def test_transfers_add_up_to_nothing(services, pesos, dollars):
    services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("1000"), date(2026, 11, 4), amount_in=usd("1"))
    )

    totals = services.dashboard.totals(TransactionFilter(is_transfer=True))

    assert (totals.income, totals.expenses, totals.unconverted) == (ars("0"), ars("0"), 0)
