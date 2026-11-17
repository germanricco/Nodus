"""Each service rule, faced with a real but uncommon case.

A rule earns its place by refusing what would break the data, never by refusing something
a person legitimately does once in a while: fix the note of an old expense in an account
that is now closed, refund exactly what is left, pay off a purchase on the day of its first
installment. For every rule, the uncommon-but-wrong case is refused with its message and
the closest legitimate case goes through.
"""

from __future__ import annotations

from datetime import date

import pytest
from factories import TODAY, ars, category_id, charge_draft, eur, expense_draft, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.bulk_changes import BulkChanges
from nodus.models.currency import Currency
from nodus.models.goal import GoalShare
from nodus.models.installment_plan import InstallmentPlan
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.errors import ValidationError
from nodus.services.planning.goal_service import GoalDraft
from nodus.services.transactions.transfer_service import TransferDraft

INCOME = TransactionType.INCOME
EXPENSE = TransactionType.EXPENSE
LAST_MONTH = date(2026, 10, 12)


def refund_draft(services, account_id, amount, expense, **overrides):
    """An income in "Reembolsos" that pays back ``expense``."""
    return income_draft(
        services, account_id, amount,
        category_id=category_id(services, "Reembolsos", INCOME), refund_of_id=expense.id,
        **overrides,
    )  # fmt: skip


@pytest.fixture
def old_expense(services, pesos):
    """A $ 1.000 grocery expense from last month."""
    return services.transactions.create(expense_draft(services, pesos.id, ars("1000"), LAST_MONTH))


class TestArchivedAccount:
    """An archived account takes no new movements, but its history stays the user's."""

    def test_an_old_expense_can_still_be_reclassified(self, services, pesos, old_expense):
        services.accounts.set_archived(pesos.id, True)
        ocio = category_id(services, "Ocio", EXPENSE)

        services.transactions.update(
            old_expense.id,
            expense_draft(
                services, pesos.id, ars("1000"), LAST_MONTH, category_id=ocio, note="Cine"
            ),
        )

        edited = services.transactions.get(old_expense.id)
        assert (edited.category_id, edited.note) == (ocio, "Cine")

    def test_bulk_edit_already_reclassifies_it(self, services, pesos, old_expense):
        """The same change through «Editar varias» goes through: the single edit is the
        odd one out."""
        services.accounts.set_archived(pesos.id, True)
        ocio = category_id(services, "Ocio", EXPENSE)

        services.bulk_edits.apply([old_expense.id], BulkChanges(category_id=ocio))

        assert services.transactions.get(old_expense.id).category_id == ocio

    def test_an_old_transfer_can_still_get_a_note(self, services, pesos, dollars):
        draft = TransferDraft(pesos.id, dollars.id, ars("120000"), LAST_MONTH, usd("100"))
        transfer = services.transfers.create(draft)
        services.accounts.set_archived(pesos.id, True)

        services.transfers.update(
            transfer.outgoing.transfer_id,
            TransferDraft(pesos.id, dollars.id, ars("120000"), LAST_MONTH, usd("100"), "Ahorro"),
        )

        assert services.transfers.get(transfer.outgoing.transfer_id).outgoing.note == "Ahorro"

    def test_a_new_movement_is_refused(self, services, pesos):
        services.accounts.set_archived(pesos.id, True)

        with pytest.raises(ValidationError, match="«Banco» está archivada"):
            services.transactions.create(expense_draft(services, pesos.id, ars("10")))

    def test_its_expense_can_be_refunded_into_an_active_account(self, services, pesos, old_expense):
        """The card was closed, the store paid back into the bank: the refund lives in an
        active account, so it goes through."""
        other = services.accounts.create("Billetera", AccountType.CASH, Currency.ARS, ars("0"))
        services.accounts.set_archived(pesos.id, True)

        refund = services.transactions.create(
            refund_draft(services, other.id, ars("1000"), old_expense)
        )

        assert services.transactions.get(refund.id).refund_of_id == old_expense.id


class TestRefunds:
    def test_a_refund_of_exactly_what_is_left_goes_through(self, services, pesos, old_expense):
        services.transactions.create(refund_draft(services, pesos.id, ars("600"), old_expense))
        services.transactions.create(refund_draft(services, pesos.id, ars("400"), old_expense))

        with pytest.raises(ValidationError, match=r"lo que queda .*: \$ 0,00"):
            services.transactions.create(refund_draft(services, pesos.id, ars("0.01"), old_expense))

    def test_an_expense_lowered_to_exactly_its_refunds_goes_through(
        self, services, pesos, old_expense
    ):
        services.transactions.create(refund_draft(services, pesos.id, ars("600"), old_expense))

        with pytest.raises(ValidationError, match=r"Ya se reembolsaron \$ 600,00"):
            services.transactions.update(
                old_expense.id, expense_draft(services, pesos.id, ars("599.99"), LAST_MONTH)
            )
        services.transactions.update(
            old_expense.id, expense_draft(services, pesos.id, ars("600"), LAST_MONTH)
        )

        assert services.transactions.get(old_expense.id).amount == ars("600")

    def test_splitting_a_refund_needs_something_over_what_is_left(
        self, services, pesos, old_expense
    ):
        """A refund of exactly what is left has nothing to set apart: it is saved as is."""
        extra = category_id(services, "Otros", INCOME)
        exact = refund_draft(services, pesos.id, ars("1000"), old_expense)

        with pytest.raises(ValidationError, match="no supera lo que queda"):
            services.transactions.save_refund_with_extra(exact, extra)
        refund, rest = services.transactions.save_refund_with_extra(
            refund_draft(services, pesos.id, ars("1000.01"), old_expense), extra
        )

        assert (refund.amount, rest.amount) == (ars("1000"), ars("0.01"))


class TestTransactions:
    def test_an_expense_turned_into_income_needs_an_income_category(
        self, services, pesos, old_expense
    ):
        """The user typed a salary as an expense: changing the type alone is refused,
        changing type and category together goes through."""
        food = old_expense.category_id

        with pytest.raises(ValidationError, match="no corresponde a este tipo"):
            services.transactions.update(
                old_expense.id,
                income_draft(services, pesos.id, ars("1000"), LAST_MONTH, category_id=food),
            )
        services.transactions.update(
            old_expense.id, income_draft(services, pesos.id, ars("1000"), LAST_MONTH)
        )

        assert services.transactions.get(old_expense.id).type is INCOME

    def test_a_transfer_leg_is_not_edited_as_a_movement(self, services, pesos):
        efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))
        transfer = services.transfers.create(TransferDraft(pesos.id, efectivo.id, ars("50"), TODAY))

        with pytest.raises(ValidationError, match="se editan como transferencia"):
            services.transactions.update(
                transfer.outgoing.id, expense_draft(services, pesos.id, ars("50"))
            )


class TestTransfers:
    def test_between_two_foreign_currencies_with_what_came_in(self, services, dollars, euros):
        """Dollars changed into euros for a trip: neither is the peso, both amounts count."""
        draft = TransferDraft(dollars.id, euros.id, usd("100"), TODAY)

        with pytest.raises(ValidationError, match="monto que entra"):
            services.transfers.create(draft)
        transfer = services.transfers.create(
            TransferDraft(dollars.id, euros.id, usd("100"), TODAY, eur("92"))
        )

        assert transfer.incoming.amount == eur("92")

    def test_a_deleted_transfer_says_so(self, services, pesos):
        efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))
        draft = TransferDraft(pesos.id, efectivo.id, ars("50"), TODAY)
        transfer = services.transfers.create(draft)
        services.transactions.delete_many([transfer.outgoing.id])

        with pytest.raises(ValidationError, match="La transferencia no existe"):
            services.transfers.update(transfer.outgoing.transfer_id, draft)


class TestInstallments:
    FIRST = date(2026, 11, 10)

    def test_paid_off_on_the_day_of_the_first_installment(self, services, pesos):
        plan = InstallmentPlan(None, 6, ars("60000"), self.FIRST)
        purchase = services.installments.create(
            expense_draft(services, pesos.id, ars("60000"), self.FIRST), plan
        )

        with pytest.raises(ValidationError, match="antes de la primera cuota"):
            services.installments.settle(purchase.id, date(2026, 11, 9))
        services.installments.settle(purchase.id, self.FIRST)

        days = {
            t.occurred_on
            for t in services.transactions.list_transactions(
                TransactionFilter(installment_plan_id=purchase.id)
            )
        }
        assert days == {self.FIRST}


class TestRecurringCharges:
    def test_a_paused_charge_can_be_edited_and_stays_paused(self, services, pesos):
        charge = services.recurring.create(charge_draft(services, pesos.id, ars("100")))
        services.recurring.set_active(charge.id, False)

        services.recurring.update(charge.id, charge_draft(services, pesos.id, ars("120")))

        edited = services.recurring.get(charge.id)
        assert (edited.amount, edited.is_active) == (ars("120"), False)
        with pytest.raises(ValidationError, match="está en pausa"):
            services.recurring.pay(charge.id, ars("120"), TODAY, pesos.id)


class TestBulkEdit:
    def test_incomes_and_expenses_together_take_a_note(self, services, pesos):
        """A trip's movements, spent and paid back, all get the same note; only a category
        would have to suit both."""
        expense = services.transactions.create(expense_draft(services, pesos.id, ars("10")))
        income = services.transactions.create(income_draft(services, pesos.id, ars("20")))

        services.bulk_edits.apply([expense.id, income.id], BulkChanges(note="Viaje"))

        assert {services.transactions.get(t.id).note for t in (expense, income)} == {"Viaje"}


class TestGoals:
    @staticmethod
    def draft(*shares, name="Vacaciones", on=date(2026, 12, 31)) -> GoalDraft:
        return GoalDraft(name, usd("2000"), on, tuple(GoalShare(a.id, p) for a, p in shares))

    def test_a_goal_past_its_date_can_still_be_edited(self, services, dollars):
        goal = services.goals.create(self.draft((dollars, 100)), TODAY)
        later = date(2027, 1, 15)

        services.goals.update(goal.id, self.draft((dollars, 100), name="Viaje"), later)

        assert services.goals.get(goal.id).name == "Viaje"

    def test_a_new_date_must_still_be_after_today(self, services, dollars):
        with pytest.raises(ValidationError, match="posterior a hoy"):
            services.goals.create(self.draft((dollars, 100), on=TODAY), TODAY)
        services.goals.create(self.draft((dollars, 100), on=date(2026, 11, 6)), TODAY)

    @pytest.mark.parametrize("percent", [0, 101])
    def test_a_share_goes_from_one_to_a_hundred(self, services, dollars, percent):
        with pytest.raises(ValidationError, match="va de 1 a 100"):
            services.goals.create(self.draft((dollars, percent)), TODAY)
        services.goals.create(self.draft((dollars, 1)), TODAY)

    def test_each_account_once(self, services, dollars):
        with pytest.raises(ValidationError, match="una sola vez"):
            services.goals.create(self.draft((dollars, 40), (dollars, 60)), TODAY)


class TestAccounts:
    def test_an_archived_investment_takes_no_new_value(self, services, investment):
        services.accounts.set_archived(investment.id, True)

        with pytest.raises(ValidationError, match="La cuenta está archivada"):
            services.accounts.adjust_value(investment.id, ars("1100000"), TODAY)
        services.accounts.set_archived(investment.id, False)
        services.accounts.adjust_value(investment.id, ars("1100000"), TODAY)

        assert services.accounts.balance(investment.id, TODAY) == ars("1100000")


class TestBudgets:
    def test_the_system_expense_category_can_carry_a_budget(self, services):
        """«Otros» is fixed but still an expense category: it can have a limit."""
        otros = category_id(services, "Otros", EXPENSE)
        services.budgets.set_limit(otros, Month.of(TODAY), ars("5000"))

        with pytest.raises(ValidationError, match="Solo las categorías de gasto"):
            services.budgets.set_limit(
                category_id(services, "Otros", INCOME), Month.of(TODAY), ars("5000")
            )
        assert services.budgets.limits_on(Month.of(TODAY))[otros] == ars("5000")
