"""Purchases in installments: what they should do and the ways they could go wrong."""

from datetime import date
from decimal import Decimal

import pytest
from factories import ars, category_id, expense_draft, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.installment_plan import InstallmentPlan
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.errors import ValidationError
from nodus.services.transaction_service import TransferDraft

FIRST = date(2026, 11, 10)
SIX = InstallmentPlan(None, 6, ars("75000"), FIRST)


def draft(services, account, **overrides):
    values = {"note": "Heladera", "payee_name": "Frávega"} | overrides
    return expense_draft(services, account.id, ars("75000"), FIRST, **values)


def installments(services, plan_id):
    found = services.transactions.list_transactions(TransactionFilter(installment_plan_id=plan_id))
    return sorted(found, key=lambda t: t.installment.number)


def database_counts(services):
    connection = services.transactions._database.connection
    plans = connection.execute("SELECT COUNT(*) FROM installment_plans").fetchone()[0]
    rows = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    return plans, rows


@pytest.fixture
def purchase(services, pesos):
    return services.installments.create(draft(services, pesos, tag_names=("Hogar",)), SIX)


class TestCreate:
    def test_one_expense_per_month_sharing_what_was_bought(self, services, pesos, purchase):
        saved = installments(services, purchase.id)

        assert [t.installment.label for t in saved] == [f"{n}/6" for n in range(1, 7)]
        assert [t.occurred_on for t in saved] == purchase.due_dates()
        assert {t.amount for t in saved} == {ars("12500")}
        assert {(t.note, t.account_id, t.type) for t in saved} == {
            ("Heladera", pesos.id, TransactionType.EXPENSE)
        }
        assert len({t.payee_id for t in saved}) == 1  # one payee, not six
        tags = services.transactions.tags_for([t.id for t in saved])
        assert all([tag.name for tag in tags[t.id]] == ["Hogar"] for t in saved)

    def test_by_installment_amount(self, services, pesos):
        plan = InstallmentPlan.from_installment_amount(ars("13000"), 6, FIRST)
        saved = services.installments.create(draft(services, pesos), plan)

        assert sum((t.amount for t in installments(services, saved.id)), ars("0")) == ars("78000")

    def test_an_uneven_total_adds_up_exactly(self, services, pesos):
        saved = services.installments.create(
            draft(services, pesos), InstallmentPlan(None, 3, ars("100"), FIRST)
        )

        assert [t.amount for t in installments(services, saved.id)] == [
            ars("33.34"), ars("33.33"), ars("33.33"),
        ]  # fmt: skip

    def test_each_installment_counts_in_its_own_month(self, services, pesos, purchase):
        for month in (Month(2026, 11), Month(2027, 4)):
            summary = services.dashboard.summary(Period.of_months(month))
            assert summary.expenses == ars("12500")

    @pytest.mark.parametrize(
        "make",
        [
            lambda s, a: income_draft(s, a.id, ars("75000"), FIRST),
            lambda s, a: draft(s, a, category_id=category_id(s, "Sueldo", TransactionType.INCOME)),
        ],
        ids=["income", "income-category"],
    )
    def test_only_an_expense(self, services, pesos, make):
        with pytest.raises(ValidationError):
            services.installments.create(make(services, pesos), SIX)
        assert database_counts(services) == (0, 0)

    def test_an_archived_account_is_rejected(self, services, pesos):
        services.accounts.set_archived(pesos.id, True)

        with pytest.raises(ValidationError):
            services.installments.create(draft(services, pesos), SIX)
        assert database_counts(services) == (0, 0)

    def test_a_total_in_another_currency_than_the_account_is_rejected(self, services, pesos):
        with pytest.raises(ValidationError):
            services.installments.create(
                draft(services, pesos), InstallmentPlan(None, 6, usd("600"), FIRST)
            )
        assert database_counts(services) == (0, 0)

    def test_all_or_nothing_when_saving_fails_halfway(self, services, pesos, monkeypatch):
        repository = services.transactions._transactions  # noqa: SLF001
        add = repository.add
        calls = []

        def failing_add(transaction):
            calls.append(transaction)
            if len(calls) == 4:
                raise RuntimeError("disk full")
            return add(transaction)

        monkeypatch.setattr(repository, "add", failing_add)

        with pytest.raises(RuntimeError):
            services.installments.create(draft(services, pesos), SIX)
        assert database_counts(services) == (0, 0)


class TestUpdate:
    def test_fields_are_copied_to_every_installment(self, services, pesos, purchase):
        first = installments(services, purchase.id)[0]
        changed = draft(services, pesos, note="Heladera No Frost", payee_name="Garbarino")

        services.installments.update(first.id, changed, SIX)

        saved = installments(services, purchase.id)
        assert {t.note for t in saved} == {"Heladera No Frost"}
        assert [t.id for t in saved][0] == first.id  # ids are kept

    def test_more_and_fewer_installments(self, services, pesos, purchase):
        first = installments(services, purchase.id)[0]

        services.installments.update(
            first.id, draft(services, pesos), InstallmentPlan(None, 3, ars("75000"), FIRST)
        )
        assert [t.amount for t in installments(services, purchase.id)] == [ars("25000")] * 3

        services.installments.update(
            first.id, draft(services, pesos), InstallmentPlan(None, 12, ars("75000"), FIRST)
        )
        saved = installments(services, purchase.id)
        assert [t.installment.label for t in saved][-1] == "12/12"
        assert sum((t.amount for t in saved), ars("0")) == ars("75000")
        assert database_counts(services) == (1, 12)

    def test_one_installment_makes_it_a_single_expense_again(self, services, pesos, purchase):
        first = installments(services, purchase.id)[0]

        services.installments.update(first.id, draft(services, pesos), None)

        single = services.transactions.get(first.id)
        assert single.installment is None
        assert single.amount == ars("75000")
        assert database_counts(services) == (0, 1)

    def test_a_single_expense_becomes_the_first_installment(self, services, pesos):
        single = services.transactions.create(draft(services, pesos))

        services.installments.update(single.id, draft(services, pesos), SIX)

        converted = services.transactions.get(single.id)
        assert converted.installment.label == "1/6"
        assert converted.amount == ars("12500")
        assert database_counts(services) == (1, 6)

    def test_an_account_in_another_currency_fails_without_changing_anything(
        self, services, pesos, dollars, purchase
    ):
        before = installments(services, purchase.id)

        with pytest.raises(ValidationError):
            services.installments.update(before[0].id, draft(services, dollars), SIX)
        assert installments(services, purchase.id) == before

    def test_an_installment_alone_cannot_be_edited(self, services, pesos, purchase):
        third = installments(services, purchase.id)[2]

        with pytest.raises(ValidationError, match="desde su compra"):
            services.transactions.update(third.id, draft(services, pesos))

    def test_bulk_editing_keeps_the_installments(self, services, pesos, purchase):
        from nodus.models.bulk_changes import BulkChanges

        ids = [t.id for t in installments(services, purchase.id)]
        services.transactions.bulk_edit(ids, BulkChanges(note="Heladera Samsung"))

        assert [t.installment.label for t in installments(services, purchase.id)] == [
            f"{n}/6" for n in range(1, 7)
        ]

    def test_a_refund_stays_on_the_first_installment(self, services, pesos):
        single = services.transactions.create(draft(services, pesos))
        refund = services.transactions.create(
            income_draft(
                services, pesos.id, ars("1000"), FIRST,
                category_id=category_id(services, "Sueldo", TransactionType.INCOME),
                refund_of_id=single.id,
            )
        )  # fmt: skip

        services.installments.update(single.id, draft(services, pesos), SIX)

        assert services.transactions.get(refund.id).refund_of_id == single.id

    def test_a_refund_larger_than_the_first_installment_is_rejected(self, services, pesos):
        single = services.transactions.create(draft(services, pesos))
        services.transactions.create(
            income_draft(
                services, pesos.id, ars("20000"), FIRST,
                category_id=category_id(services, "Sueldo", TransactionType.INCOME),
                refund_of_id=single.id,
            )
        )  # fmt: skip

        with pytest.raises(ValidationError):
            services.installments.update(single.id, draft(services, pesos), SIX)
        assert services.transactions.get(single.id).installment is None
        assert database_counts(services) == (0, 2)


class TestPayingOff:
    def test_settle_and_unsettle_come_back_to_the_same_calendar(self, services, pesos, purchase):
        before = [t.occurred_on for t in installments(services, purchase.id)]

        services.installments.settle(purchase.id, date(2026, 12, 20))
        settled = [t.occurred_on for t in installments(services, purchase.id)]
        assert settled == before[:2] + [date(2026, 12, 20)] * 4

        services.installments.unsettle(purchase.id)
        assert [t.occurred_on for t in installments(services, purchase.id)] == before

    def test_before_the_first_installment_is_rejected(self, services, pesos, purchase):
        with pytest.raises(ValidationError):
            services.installments.settle(purchase.id, date(2026, 11, 1))

    def test_editing_keeps_it_paid_off(self, services, pesos, purchase):
        services.installments.settle(purchase.id, date(2026, 12, 20))
        first = installments(services, purchase.id)[0]

        services.installments.update(first.id, draft(services, pesos, note="Otra"), SIX)

        assert installments(services, purchase.id)[-1].occurred_on == date(2026, 12, 20)


class TestDelete:
    def test_deleting_one_installment_deletes_the_purchase(self, services, pesos, purchase):
        services.transactions.delete(installments(services, purchase.id)[3].id)

        assert database_counts(services) == (0, 0)

    def test_two_installments_and_another_row_at_once(self, services, pesos, purchase):
        other = services.transactions.create(expense_draft(services, pesos.id, ars("10"), FIRST))
        keep = services.transactions.create(expense_draft(services, pesos.id, ars("20"), FIRST))
        first, second = installments(services, purchase.id)[:2]

        services.transactions.delete_many([first.id, second.id, other.id])

        assert database_counts(services) == (0, 1)
        assert services.transactions.get(keep.id).amount == ars("20")

    def test_deleting_the_account_leaves_no_plan_behind(self, services, pesos, purchase):
        services.accounts.delete(pesos.id)

        assert database_counts(services) == (0, 0)

    def test_deleting_the_purchase_leaves_its_refund_as_income(self, services, pesos, purchase):
        first = installments(services, purchase.id)[0]
        refund = services.transactions.create(
            income_draft(
                services, pesos.id, ars("1000"), FIRST,
                category_id=category_id(services, "Sueldo", TransactionType.INCOME),
                refund_of_id=first.id,
            )
        )  # fmt: skip

        services.transactions.delete(first.id)

        assert services.transactions.get(refund.id).refund_of_id is None

    def test_deleting_the_category_moves_the_installments(self, services, pesos):
        groceries = category_id(services, "Supermercado y comida", TransactionType.EXPENSE)
        plan = services.installments.create(draft(services, pesos), SIX)

        services.categories.delete(groceries)

        moved = {t.category_id for t in installments(services, plan.id)}
        assert len(moved) == 1
        assert services.categories.get(moved.pop()).is_system


class TestProgress:
    def test_summary_says_how_far_it_goes(self, services, pesos, purchase):
        (summary,) = services.installments.summaries(date(2027, 1, 15))

        assert summary.paid == 3
        assert summary.upcoming.installment.label == "4/6"
        assert summary.remaining == ars("37500")
        assert summary.first.note == "Heladera"

    def test_a_finished_purchase_is_not_listed(self, services, pesos, purchase):
        assert services.installments.summaries(date(2027, 4, 10)) == []

    def test_pending_for_the_account(self, services, pesos, dollars, purchase):
        assert services.installments.pending_for_account(pesos.id, FIRST) == ars("62500")
        assert services.installments.pending_for_account(dollars.id, FIRST) is None

    def test_installments_are_not_in_todays_balance_until_their_day(
        self, services, pesos, purchase
    ):
        assert services.accounts.balance(pesos.id, FIRST) == ars("87500")
        assert services.accounts.balance(pesos.id, date(2026, 12, 9)) == ars("87500")
        assert services.accounts.balance(pesos.id, date(2026, 12, 10)) == ars("75000")


class TestOtherCurrencies:
    def test_dollar_installments_convert_at_the_rate_of_their_day(self, services, dollars):
        services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1000"))
        services.exchange_rates.set_rate(date(2026, 12, 1), Decimal("1200"))
        services.installments.create(
            expense_draft(services, dollars.id, usd("60"), FIRST),
            InstallmentPlan(None, 2, usd("60"), FIRST),
        )

        november = services.dashboard.summary(Period.of_months(Month(2026, 11)))
        december = services.dashboard.summary(Period.of_months(Month(2026, 12)))

        assert (november.expenses, december.expenses) == (ars("30000"), ars("36000"))


def test_a_transfer_leg_can_never_be_an_installment(services, pesos, dollars):
    """The model refuses it, whatever path tries."""
    import dataclasses

    from nodus.models.installment_plan import Installment

    transfer = services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("1000"), FIRST, amount_in=usd("1"))
    )
    with pytest.raises(ValueError):
        dataclasses.replace(transfer.outgoing, installment=Installment(1, 1, 2))


def test_an_unknown_plan_says_so(services):
    with pytest.raises(Exception, match="no existe"):
        services.installments.settle(999, FIRST)


def test_cash_account_works_too(services):
    cash = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))
    plan = services.installments.create(draft(services, cash), SIX)

    assert len(installments(services, plan.id)) == 6
