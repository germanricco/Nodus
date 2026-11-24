"""Business rules for income and expenses: saving, editing, deleting and reading them.

Transfers, refunds and editing several at once have services of their own, next to this
one.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date, datetime

from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.database.repositories.tag_repository import TagRepository
from nodus.database.repositories.transaction_repository import (
    TransactionFilter,
    TransactionRepository,
)
from nodus.i18n import _
from nodus.models.account import Account
from nodus.models.money import Money
from nodus.models.period import Month, Period
from nodus.models.tag import Tag
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.backups.backup_service import LARGE_DELETE, BackupService
from nodus.services.errors import ValidationError, require_found, require_in_calendar
from nodus.services.transactions.account_rules import active_account, require_amount_for
from nodus.services.transactions.labels import MovementLabels
from nodus.services.transactions.refund_service import RefundService


@dataclass(frozen=True)
class TransactionDraft:
    """What the user fills in for an income or an expense.

    ``payee_name`` is the name as typed: saving finds the payee with that name, or creates
    it. An empty name leaves the transaction without a payee. ``tag_names`` work the same
    way, one tag per name. ``refund_of_id`` makes an income the refund of that expense;
    an expense ignores it.
    """

    account_id: int
    type: TransactionType
    amount: Money
    occurred_on: date
    category_id: int
    note: str = ""
    payee_name: str = ""
    refund_of_id: int | None = None
    tag_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class AccountActivity:
    """What came into and went out of one account in a stretch of days, in its currency.
    Transfers count, since for the account they are money in or out like any other;
    ``transfers_in`` and ``transfers_out`` say how much of it they were."""

    incoming: Money
    outgoing: Money
    transfers_in: Money
    transfers_out: Money


class TransactionService:
    """Income and expenses: their checks, saving them with payee and tags, and reading
    them back for lists and figures."""

    def __init__(
        self,
        database: Database,
        transactions: TransactionRepository,
        accounts: AccountRepository,
        categories: CategoryRepository,
        tags: TagRepository,
        labels: MovementLabels,
        refunds: RefundService,
        backups: BackupService,
    ) -> None:
        self._backups = backups
        self._database = database
        self._transactions = transactions
        self._accounts = accounts
        self._categories = categories
        self._tags = tags
        self._labels = labels
        self._refunds = refunds

    # Income and expenses

    def create(self, draft: TransactionDraft) -> Transaction:
        transaction = self._build_transaction(None, draft)
        with self._database.transaction():
            return self.stage(transaction, draft)

    def validated(self, draft: TransactionDraft, transaction_id: int | None = None) -> Transaction:
        """The transaction ``draft`` describes, checked against the rules but not saved, for
        services that save it together with other changes. Its payee is not resolved.
        ``transaction_id`` is the one it would replace, so its refunds are checked too."""
        return self._build_transaction(transaction_id, draft)

    def stage(self, transaction: Transaction, draft: TransactionDraft) -> Transaction:
        """Saves a validated ``transaction`` (added without an id, updated with one) with the
        payee and tags of ``draft``, inside the database transaction the caller opened, for
        services that save several together, as the installments of a purchase."""
        transaction = self._labels.with_payee(transaction, draft.payee_name)
        if transaction.id is None:
            transaction = self._transactions.add(transaction)
        else:
            self._transactions.update(transaction)
        self._labels.set_tags(transaction.id, draft.tag_names)
        return transaction

    def update(self, transaction_id: int, draft: TransactionDraft) -> None:
        transaction = self._edited(transaction_id, draft)
        with self._database.transaction():
            self._stage_edit(transaction, draft)

    def save_refund_with_extra(
        self,
        draft: TransactionDraft,
        extra_category_id: int,
        transaction_id: int | None = None,
    ) -> tuple[Transaction, Transaction]:
        """Saves a refund that goes over what is left of its expense as two incomes,
        together: the refund of what was left, and the rest, apart, in
        ``extra_category_id``, with the same account, day, payee, note and tags. So the
        expense ends fully refunded and never below zero. ``transaction_id`` is the
        refund being edited, if any."""
        excess = self._refunds.excess(draft, transaction_id)
        if excess is None:
            raise ValidationError(
                _("Ese reembolso no supera lo que queda del gasto."), field="amount"
            )
        refund_draft = dataclasses.replace(draft, amount=draft.amount - excess)
        extra_draft = dataclasses.replace(
            draft, amount=excess, category_id=extra_category_id, refund_of_id=None
        )
        refund = (
            self._build_transaction(None, refund_draft)
            if transaction_id is None
            else self._edited(transaction_id, refund_draft)
        )
        extra = self._build_transaction(None, extra_draft)
        with self._database.transaction():
            if transaction_id is None:
                refund = self.stage(refund, refund_draft)
            else:
                refund = self._stage_edit(refund, refund_draft)
            extra = self.stage(extra, extra_draft)
        return refund, extra

    def _edited(self, transaction_id: int, draft: TransactionDraft) -> Transaction:
        """Transaction ``transaction_id`` as ``draft`` leaves it, checked, not saved."""
        current = self.get(transaction_id)
        if current.is_transfer:
            raise ValidationError(_("Las transferencias se editan como transferencia."))
        if current.installment is not None:
            raise ValidationError(_("Las cuotas se editan desde su compra."))
        return self._build_transaction(transaction_id, draft)

    def _stage_edit(self, transaction: Transaction, draft: TransactionDraft) -> Transaction:
        """Saves an edited ``transaction`` inside the caller's database transaction."""
        if transaction.type is TransactionType.INCOME:
            # An expense turned into income can no longer be refunded.
            self._transactions.unlink_refunds_of(transaction.id)
        return self.stage(transaction, draft)

    def delete_many(self, transaction_ids: list[int]) -> None:
        """Deletes every one of ``transaction_ids`` together, or none if one is missing.

        A transfer goes whole, even when both of its legs are listed, and so does a purchase
        in installments: the installments are one purchase, never half of one. Deleting
        ``LARGE_DELETE`` or more copies the data first, and the copy is kept for a month.
        """
        transactions = [self.get(transaction_id) for transaction_id in transaction_ids]
        if len(transactions) >= LARGE_DELETE:
            self._backups.create_before_delete(datetime.now())
        transfer_ids = {t.transfer_id for t in transactions if t.is_transfer}
        plan_ids = {t.installment.plan_id for t in transactions if t.installment}
        with self._database.transaction():
            for transfer_id in transfer_ids:
                self._transactions.delete_transfer(transfer_id)
            for plan_id in plan_ids:
                self._transactions.delete_installments(plan_id)
            for transaction in transactions:
                if not transaction.is_transfer and transaction.installment is None:
                    self._transactions.delete(transaction.id)

    def tags_for(self, transaction_ids: list[int]) -> dict[int, list[Tag]]:
        """The tags of each of ``transaction_ids`` by name, read at once for lists."""
        return self._tags.tags_for(transaction_ids)

    def get(self, transaction_id: int) -> Transaction:
        return require_found(self._transactions.get(transaction_id), _("La transacción no existe."))

    def list_transactions(self, criteria: TransactionFilter) -> list[Transaction]:
        return self._transactions.list(criteria)

    def last_expense(self) -> Transaction | None:
        """The expense recorded last, whatever its day, to record it again; never an
        installment, which belongs to a purchase."""
        expenses = self._transactions.list(
            TransactionFilter(type=TransactionType.EXPENSE, is_transfer=False)
        )
        return max((t for t in expenses if t.installment is None), key=lambda t: t.id, default=None)

    def account_activity(self, account: Account, start: date, end: date) -> AccountActivity:
        """What came into and went out of ``account`` from ``start`` to ``end``."""
        zero = Money.zero(account.currency)
        totals = {(kind, transfer): zero for kind in TransactionType for transfer in (False, True)}
        criteria = TransactionFilter(account_id=account.id, start=start, end=end)
        for transaction in self._transactions.list(criteria):
            key = (transaction.type, transaction.is_transfer)
            totals[key] += transaction.amount
        income, expense = TransactionType.INCOME, TransactionType.EXPENSE
        return AccountActivity(
            totals[income, False] + totals[income, True],
            totals[expense, False] + totals[expense, True],
            totals[income, True],
            totals[expense, True],
        )

    def date_range(self, criteria: TransactionFilter) -> tuple[date, date] | None:
        """The first and last day of the transactions matching ``criteria``, if any."""
        return self._transactions.date_range(criteria)

    def first_month(self) -> Month | None:
        """The month of the first movement: no chart starts before it."""
        span = self.date_range(TransactionFilter())
        return Month.of(span[0]) if span else None

    def history_months(self, period: Period, today: date | None = None) -> list[Month]:
        """The months of ``period`` with a history (``Period.months_since``): what a monthly
        average divides by. None of them before the first movement."""
        span = self.date_range(TransactionFilter())
        if span is None:
            return []
        return period.months_since(span[0], today or date.today())

    def get_many(self, transaction_ids: list[int]) -> dict[int, Transaction]:
        """The transactions with these ids, by id, read together: a list shows many."""
        return {t.id: t for t in self._transactions.get_many(transaction_ids)}

    # Validation

    def _build_transaction(
        self, transaction_id: int | None, draft: TransactionDraft
    ) -> Transaction:
        current = self._transactions.get(transaction_id) if transaction_id is not None else None
        kept_id = current.account_id if current is not None else None
        account = active_account(self._accounts, draft.account_id, "account_id", kept_id)
        require_amount_for(draft.amount, account, "amount")
        require_in_calendar(draft.occurred_on, "occurred_on")
        category = require_found(
            self._categories.get(draft.category_id), _("La categoría no existe.")
        )
        if category.kind is not draft.type:
            raise ValidationError(
                _("La categoría «{category}» no corresponde a este tipo de transacción.").format(
                    category=category.name
                ),
                field="category_id",
            )
        income = draft.type is TransactionType.INCOME
        refund_of_id = draft.refund_of_id if income else None
        if refund_of_id is not None:
            self._require_refundable(refund_of_id, transaction_id, draft.amount)
        if not income and transaction_id is not None:
            self._require_covers_refunds(transaction_id, draft.amount)
        return Transaction(
            id=transaction_id,
            account_id=account.id,
            type=draft.type,
            amount=draft.amount,
            occurred_on=draft.occurred_on,
            category_id=category.id,
            note=draft.note.strip(),
            refund_of_id=refund_of_id,
        )

    def _require_refundable(self, expense_id: int, refund_id: int | None, amount: Money) -> None:
        """The refund of ``amount`` fits what is left of the expense, when both share a
        currency."""
        expense = self._transactions.get(expense_id)
        if expense is None or expense.is_transfer or expense.type is not TransactionType.EXPENSE:
            raise ValidationError(_("Un reembolso tiene que devolver un gasto."))
        summary = self._refunds.summary(expense_id, ignore_id=refund_id)
        if amount.currency is expense.amount.currency and amount > summary.remaining:
            raise ValidationError(
                _(
                    "El reembolso supera lo que queda por reembolsar de ese gasto: {remaining}."
                ).format(remaining=summary.remaining.format()),
                field="amount",
            )

    def _require_covers_refunds(self, expense_id: int, amount: Money) -> None:
        """An expense cannot become smaller than what has already been refunded of it."""
        refunded = self._refunds.summary(expense_id).refunded
        if amount.currency is refunded.currency and amount < refunded:
            raise ValidationError(
                _(
                    "Ya se reembolsaron {refunded} de este gasto: el monto no puede ser menor."
                ).format(refunded=refunded.format()),
                field="amount",
            )
