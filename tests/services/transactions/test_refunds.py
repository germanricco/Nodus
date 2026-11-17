"""Refunds: an income linked to the expense it pays back counts as less spending."""

from datetime import date
from decimal import Decimal

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.errors import ValidationError
from nodus.services.reports.analysis_service import Metric
from nodus.services.transactions.transaction_service import TransferDraft

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


class TestRefundWithExtra:
    """A friend sends $ 1.000 for a $ 998 share: the refund keeps $ 998, the rest is apart."""

    @pytest.fixture
    def share(self, services, pesos):
        return services.transactions.create(
            expense_draft(services, pesos.id, ars("998"), date(2026, 10, 20))
        )

    def others(self, services):
        return category_id(services, "Otros", INCOME)

    def test_excess_over_what_is_left(self, services, pesos, dollars, share):
        excess = services.transactions.refund_excess
        assert excess(refund_draft(services, pesos.id, ars("1000"), share)) == ars("2")
        assert excess(refund_draft(services, pesos.id, ars("998"), share)) is None
        assert excess(refund_draft(services, dollars.id, usd("1000"), share)) is None
        assert excess(income_draft(services, pesos.id, ars("1000"))) is None

    def test_saves_the_refund_and_the_rest(self, services, pesos, share):
        draft = refund_draft(
            services, pesos.id, ars("1000"), share, note="Entradas", payee_name="Ana",
            tag_names=("Juntada",),
        )  # fmt: skip

        refund, extra = services.transactions.save_refund_with_extra(draft, self.others(services))

        assert (refund.amount, refund.refund_of_id) == (ars("998"), share.id)
        assert (extra.amount, extra.refund_of_id, extra.category_id) == (
            ars("2"), None, self.others(services),
        )  # fmt: skip
        assert (extra.account_id, extra.occurred_on, extra.note) == (
            pesos.id, draft.occurred_on, "Entradas",
        )  # fmt: skip
        assert extra.payee_id == refund.payee_id is not None
        tags = services.transactions.tags_for([extra.id])[extra.id]
        assert [tag.name for tag in tags] == ["Juntada"]
        assert services.transactions.refund_summary(share.id).remaining == ars("0")

    def test_raising_an_edited_refund(self, services, pesos, share):
        first = services.transactions.create(refund_draft(services, pesos.id, ars("500"), share))

        refund, extra = services.transactions.save_refund_with_extra(
            refund_draft(services, pesos.id, ars("1000"), share), self.others(services), first.id
        )

        assert refund.id == first.id
        assert services.transactions.get(first.id).amount == ars("998")
        assert extra.amount == ars("2")

    def test_rejects_an_expense_category_and_saves_nothing(self, services, pesos, share):
        draft = refund_draft(services, pesos.id, ars("1000"), share)
        expense_category = category_id(services, "Otros", EXPENSE)

        with pytest.raises(ValidationError, match="no corresponde"):
            services.transactions.save_refund_with_extra(draft, expense_category)
        assert services.transactions.refund_summary(share.id).refunds == []

    def test_only_when_it_goes_over(self, services, pesos, share):
        draft = refund_draft(services, pesos.id, ars("998"), share)
        with pytest.raises(ValidationError, match="no supera"):
            services.transactions.save_refund_with_extra(draft, self.others(services))


def test_still_refundable_leaves_out_what_is_refunded_in_full(services, pesos, purchase):
    other = services.transactions.create(
        expense_draft(services, pesos.id, ars("500"), date(2026, 10, 21))
    )
    services.transactions.create(refund_draft(services, pesos.id, ars("1000"), purchase))
    services.transactions.create(refund_draft(services, pesos.id, ars("100"), other))

    assert services.transactions.still_refundable([purchase, other]) == [other]
    assert services.transactions.still_refundable([purchase, other], purchase.id) == [
        purchase,
        other,
    ]
