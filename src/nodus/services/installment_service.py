"""Purchases paid in monthly installments: saving them, changing them and their progress."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.installment_plan_repository import InstallmentPlanRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.models.currency import Currency
from nodus.models.installment_plan import Installment, InstallmentPlan
from nodus.models.money import Money
from nodus.models.transaction import Transaction, TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.errors import ValidationError, require_found
from nodus.services.transaction_service import TransactionDraft, TransactionService


@dataclass(frozen=True)
class InstallmentSummary:
    """Where a purchase in installments stands on a day.

    ``upcoming`` is the next installment to come off the account, or None once all have.
    """

    plan: InstallmentPlan
    installments: list[Transaction]
    paid: int
    upcoming: Transaction | None
    remaining: Money

    @property
    def first(self) -> Transaction:
        """The first installment, which names the purchase, its account and category."""
        return self.installments[0]

    @property
    def is_finished(self) -> bool:
        return self.upcoming is None


class InstallmentService:
    """Saves a purchase as one expense per installment, each on its own month.

    Every installment is created on saving, dated in the future: the balance of today
    leaves them out (``AccountService.balances``), so each one comes off the account on its
    day without anything to run. The plan keeps the calendar; the rest (account, category,
    payee, note, tags) lives on the installments, written through ``TransactionService`` so
    they follow the same rules as any expense.
    """

    def __init__(
        self,
        database: Database,
        plans: InstallmentPlanRepository,
        transaction_repository: TransactionRepository,
        transactions: TransactionService,
    ) -> None:
        self._database = database
        self._plans = plans
        self._transaction_repository = transaction_repository
        self._transactions = transactions

    def create(self, draft: TransactionDraft, plan: InstallmentPlan) -> InstallmentPlan:
        """Saves the purchase ``draft`` describes in the installments of ``plan``; the
        draft's amount and date are taken from the plan."""
        self._require_expense(draft)
        with self._database.transaction():
            saved = self._plans.add(plan)
            self._write(saved, [], draft)
        return saved

    def update(
        self, transaction_id: int, draft: TransactionDraft, plan: InstallmentPlan | None
    ) -> None:
        """Saves the purchase that ``transaction_id`` belongs to, as one installment of it or
        as a single expense.

        With a ``plan``, a single expense becomes its first installment and a purchase gets
        the new calendar; without one, the purchase becomes a single expense again (its
        first installment, with the draft's amount and date). Installments keep their ids,
        so their refunds stay linked.
        """
        current = self._transactions.get(transaction_id)
        self._require_expense(draft)
        installments = self._installments_of(current)
        old_plan = self._plans.get(current.installment.plan_id) if current.installment else None
        with self._database.transaction():
            if plan is None:
                first = self._transactions.validated(draft, installments[0].id)
                self._transactions.stage(first, draft)
                for extra in installments[1:]:
                    self._transaction_repository.delete(extra.id)
                return
            if old_plan is not None:
                plan = dataclasses.replace(plan, id=old_plan.id, settled_on=_kept(old_plan, plan))
                self._plans.update(plan)
            else:
                plan = self._plans.add(plan)
            self._write(plan, installments, draft)

    def settle(self, plan_id: int, day: date) -> None:
        """Pays off the rest of the purchase on ``day``: the installments due after it fall
        on that day. ``unsettle`` undoes it."""
        plan = self._plan(plan_id)
        if day < plan.first_due_on:
            raise ValidationError("No se puede adelantar antes de la primera cuota.")
        self._redate(dataclasses.replace(plan, settled_on=day))

    def unsettle(self, plan_id: int) -> None:
        """Brings back the calendar of the purchase as it was before paying it off."""
        self._redate(dataclasses.replace(self._plan(plan_id), settled_on=None))

    def plan(self, plan_id: int) -> InstallmentPlan:
        return self._plan(plan_id)

    def summaries(self, today: date) -> list[InstallmentSummary]:
        """Every purchase with installments still to come, the soonest first."""
        summaries = [self._summary(plan, today) for plan in self._plans.list()]
        active = [s for s in summaries if not s.is_finished]
        return sorted(active, key=lambda s: (s.upcoming.occurred_on, s.plan.id))

    def monthly(self, today: date) -> list[Money]:
        """What the next installment of every purchase adds up to, one amount per currency:
        what installments take each month."""
        totals: dict[Currency, Money] = {}
        for summary in self.summaries(today):
            amount = summary.upcoming.amount
            totals[amount.currency] = (
                totals.get(amount.currency, Money.zero(amount.currency)) + amount
            )
        return list(totals.values())

    def pending_for_account(self, account_id: int, today: date) -> Money | None:
        """What is still to come off ``account_id`` in installments; None when nothing."""
        pending = [s.remaining for s in self.summaries(today) if s.first.account_id == account_id]
        return sum(pending[1:], pending[0]) if pending else None

    # Internals

    def _write(
        self, plan: InstallmentPlan, installments: list[Transaction], draft: TransactionDraft
    ) -> None:
        """Writes the installments of ``plan`` from ``draft`` over ``installments`` (reusing
        their ids in order), adding the missing ones and deleting the extra."""
        for (number, day, amount), existing in zip(
            plan.schedule(), installments + [None] * plan.count, strict=False
        ):
            transaction_id = existing.id if existing else None
            installment = self._transactions.validated(
                dataclasses.replace(draft, amount=amount, occurred_on=day), transaction_id
            )
            self._transactions.stage(
                dataclasses.replace(
                    installment, installment=Installment(plan.id, number, plan.count)
                ),
                draft,
            )
        for extra in installments[plan.count :]:
            self._transaction_repository.delete(extra.id)

    def _redate(self, plan: InstallmentPlan) -> None:
        """Saves ``plan`` and moves its installments to its days; nothing else changes."""
        installments = self._installments(plan.id)
        with self._database.transaction():
            self._plans.update(plan)
            for transaction, day in zip(installments, plan.due_dates(), strict=True):
                self._transaction_repository.update(
                    dataclasses.replace(transaction, occurred_on=day)
                )

    def _summary(self, plan: InstallmentPlan, today: date) -> InstallmentSummary:
        installments = self._installments(plan.id)
        upcoming = next((t for t in installments if t.occurred_on > today), None)
        return InstallmentSummary(
            plan, installments, plan.due_count(today), upcoming, plan.remaining(today)
        )

    def _installments_of(self, transaction: Transaction) -> list[Transaction]:
        if transaction.installment is None:
            return [transaction]
        return self._installments(transaction.installment.plan_id)

    def _installments(self, plan_id: int) -> list[Transaction]:
        """The installments of a purchase, in order."""
        found = self._transactions.list_transactions(TransactionFilter(installment_plan_id=plan_id))
        return sorted(found, key=lambda t: t.installment.number)

    def _plan(self, plan_id: int) -> InstallmentPlan:
        return require_found(self._plans.get(plan_id), "La compra en cuotas no existe.")

    @staticmethod
    def _require_expense(draft: TransactionDraft) -> None:
        if draft.type is not TransactionType.EXPENSE:
            raise ValidationError("Solo un gasto se paga en cuotas.")


def _kept(old: InstallmentPlan, new: InstallmentPlan) -> date | None:
    """The day the purchase was paid off, while it still fits the new calendar."""
    settled = old.settled_on
    return settled if settled is not None and settled >= new.first_due_on else None
