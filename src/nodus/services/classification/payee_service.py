"""Business rules for payees: unique names, merging and what each one adds up to."""

from __future__ import annotations

import dataclasses
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from nodus.database.database import Database
from nodus.database.repositories.payee_repository import PayeeRepository
from nodus.i18n import N_, _
from nodus.models.category import Category
from nodus.models.payee import Payee, PayeeUsage
from nodus.models.period import Period, latest_until
from nodus.models.transaction import Transaction, TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.app.undo_service import UndoService
from nodus.services.classification.category_service import CategoryService
from nodus.services.classification.named_records import NamedRecordService
from nodus.services.conversion import PeriodTotals, period_totals
from nodus.services.errors import clean_name, require_free_name
from nodus.services.sorting import name_sort_key, rank_matches
from nodus.services.transactions.transaction_service import TransactionService


@dataclass(frozen=True)
class PayeeSummary:
    """A payee with its transactions added up, for its row and its page.

    ``totals`` are those of a period (income minus expenses in pesos, dollars at the rate
    of their day); ``count`` is how many it has over its whole history. ``top_category``
    is the one used most with this payee, and ``first_on`` and ``last_on`` the dates of its
    first and latest transactions (None while it has none), ``latest_on`` the latest one
    up to today, what «Último movimiento» shows: an installment still to come has not
    happened yet.
    """

    payee: Payee
    count: int
    totals: PeriodTotals
    top_category: Category | None
    first_on: date | None
    last_on: date | None
    latest_on: date | None

    @property
    def kind(self) -> TransactionType:
        """Whether the user pays this payee or is paid by it: the kind of its usual
        category; without one, the sign of its total in the period. One with neither
        counts as an expense, the usual case."""
        if self.top_category is not None:
            return self.top_category.kind
        income = self.totals.net.cents > 0
        return TransactionType.INCOME if income else TransactionType.EXPENSE


class PayeeService(NamedRecordService[Payee]):
    """Payees: suggestions while typing, the category each one usually takes, and what
    the user spent or received with each."""

    NOT_FOUND_TEXT = N_("El beneficiario no existe.")
    NO_OTHER_TEXT = N_("Elige otro beneficiario para unir.")
    NAME_TAKEN_TEXT = N_("Ya hay otro beneficiario «{name}», así que no se puede deshacer.")

    # How far back use orders the suggestions while typing, and before typing anything:
    # the latter shows only what is used now, a few of them.
    MATCHES_DAYS = 365
    FREQUENT_DAYS = 90
    FREQUENT_COUNT = 6

    def __init__(
        self,
        database: Database,
        payees: PayeeRepository,
        transactions: TransactionService,
        categories: CategoryService,
        exchange_rates: ExchangeRateService,
        undo: UndoService,
    ) -> None:
        super().__init__(database, payees)
        self._payees = payees
        self._undo = undo
        self._transactions = transactions
        self._categories = categories
        self._exchange_rates = exchange_rates

    def list_payees(self) -> list[Payee]:
        """Every payee in alphabetical order."""
        return self._sorted()

    def matches(
        self,
        text: str,
        kind: TransactionType | None = None,
        category_id: int | None = None,
        today: date | None = None,
    ) -> list[Payee]:
        """Payees whose name contains ``text``, those starting with it first. For a
        ``kind`` of transaction, the ones used with ``category_id`` come next, then the
        most used and latest in that kind over the last year, then the rest
        alphabetically."""
        if kind is None:
            return rank_matches(self._payees.list(), text)
        usage = self._usage(kind, self.MATCHES_DAYS, today)
        return rank_matches(
            self._payees.list(), text, then=lambda p: _by_use(usage.get(p.id), category_id)
        )

    def frequent(
        self, kind: TransactionType, category_id: int | None = None, today: date | None = None
    ) -> list[Payee]:
        """What to suggest before anything is typed: the payees most used in ``kind``
        transactions lately, those used with ``category_id`` first. None if nothing was."""
        usage = self._usage(kind, self.FREQUENT_DAYS, today)
        used = [payee for payee in self._payees.list() if payee.id in usage]
        used.sort(key=lambda p: (_by_use(usage[p.id], category_id), name_sort_key(p.name)))
        return used[: self.FREQUENT_COUNT]

    def _usage(self, kind: TransactionType, days: int, today: date | None) -> dict[int, PayeeUsage]:
        until = today or date.today()
        return self._payees.usage(kind, until - timedelta(days=days), until)

    def create(self, name: str, default_category_id: int | None = None) -> Payee:
        payee = self._checked(Payee(None, clean_name(name), default_category_id))
        with self._database.transaction():
            return self._payees.add(payee)

    def update(self, payee_id: int, name: str, default_category_id: int | None) -> None:
        current = self.get(payee_id)
        payee = self._checked(
            dataclasses.replace(
                current, name=clean_name(name), default_category_id=default_category_id
            )
        )
        with self._database.transaction():
            self._payees.update(payee)

    def transaction_count(self, payee_id: int) -> int:
        return self._payees.count_transactions(payee_id)

    def _affected(self, payee_ids: list[int]) -> int:
        """Deleting payees leaves their transactions without one."""
        return sum(self._payees.count_transactions(payee_id) for payee_id in payee_ids)

    def merge_many(self, source_ids: list[int], target_id: int) -> None:
        """Moves the transactions of every one of ``source_ids`` to ``target_id`` and
        deletes the sources, all together.

        The target keeps its default category, or takes the first source's that has one.
        It can be undone.
        """
        sources, target = self._merge_parties(source_ids, target_id)
        inherited = next(
            (s.default_category_id for s in sources if s.default_category_id is not None), None
        )
        rows = [self._payees.row(source.id) for source in sources]
        moved = [self._payees.transaction_ids(source.id) for source in sources]
        with self._database.transaction():
            for source in sources:
                self._payees.reassign(source.id, target_id)
                self._payees.delete(source.id)
            if target.default_category_id is None and inherited is not None:
                self._payees.update(dataclasses.replace(target, default_category_id=inherited))
            merged = self._payees.get(target_id)
        self._undo.offer(
            _("Se unieron {count} beneficiarios en {target}.").format(
                count=len(sources) + 1, target=target.name
            ),
            lambda: self._unmerge(target, merged, rows, moved),
        )

    def _unmerge(
        self,
        target: Payee,
        merged: Payee | None,
        rows: list[dict[str, Any]],
        moved: list[list[int]],
    ) -> None:
        """Undoes ``merge_many``: the merged payees back, with their own id and their
        transactions, and the target's default category as it was."""
        held = set(self._payees.transaction_ids(target.id))
        self._require_restorable(target, merged, rows, [set(m) for m in moved], held)
        for row, transaction_ids in zip(rows, moved, strict=True):
            self._payees.put_back(row)
            self._payees.assign(transaction_ids, row["id"])
        self._payees.update(target)

    def suggested_category(self, payee_id: int, kind: TransactionType) -> int | None:
        """The category for a new ``kind`` transaction with this payee: its default if it is
        of that kind, otherwise the one of its latest ``kind`` transaction."""
        payee = self.get(payee_id)
        default = payee.default_category_id
        if default is not None and self._categories.get(default).kind is kind:
            return default
        latest = self._transactions.list_transactions(
            TransactionFilter(payee_id=payee_id, type=kind, is_transfer=False, limit=1)
        )
        return latest[0].category_id if latest else None

    def summaries(self, period: Period) -> list[PayeeSummary]:
        """Every payee with its totals in ``period``, the most used there first."""
        by_payee: dict[int, list[Transaction]] = defaultdict(list)
        for transaction in self._transactions.list_transactions(
            TransactionFilter(is_transfer=False)
        ):
            if transaction.payee_id is not None:
                by_payee[transaction.payee_id].append(transaction)
        categories = {c.id: c for c in self._categories.list_categories()}
        summaries = [
            self._summary(p, by_payee[p.id], categories, period) for p in self._payees.list()
        ]
        return sorted(summaries, key=lambda s: (-s.totals.count, name_sort_key(s.payee.name)))

    def summary(self, payee_id: int, period: Period) -> PayeeSummary:
        """One payee with its totals in ``period``, for its own page."""
        payee = self.get(payee_id)
        transactions = self._transactions.list_transactions(
            TransactionFilter(payee_id=payee_id, is_transfer=False)
        )
        categories = {c.id: c for c in self._categories.list_categories()}
        return self._summary(payee, transactions, categories, period)

    def _summary(
        self,
        payee: Payee,
        transactions: list[Transaction],
        categories: dict[int, Category],
        period: Period,
    ) -> PayeeSummary:
        usage = Counter(t.category_id for t in transactions).most_common(1)
        return PayeeSummary(
            payee=payee,
            count=len(transactions),
            totals=period_totals(transactions, period, self._exchange_rates),
            top_category=categories[usage[0][0]] if usage else None,
            first_on=min((t.occurred_on for t in transactions), default=None),
            last_on=max((t.occurred_on for t in transactions), default=None),
            latest_on=latest_until((t.occurred_on for t in transactions), date.today()),
        )

    def _checked(self, payee: Payee) -> Payee:
        """``payee`` if its name is usable and no other payee has it."""
        hint = _("; para juntarlos usa «Unir con…»") if payee.id is not None else ""
        require_free_name(
            payee.id,
            payee.normalized_name,
            self._payees.find_by_normalized,
            lambda name: _("Ya existe «{name}»{hint}.").format(name=name, hint=hint),
        )
        if payee.default_category_id is not None:
            self._categories.get(payee.default_category_id)
        return payee


def _by_use(usage: PayeeUsage | None, category_id: int | None) -> tuple[int, int, int]:
    """Sort key: used with ``category_id`` most, then used most, then latest first."""
    if usage is None:
        return (0, 0, 0)
    return (-usage.uses_with(category_id), -usage.uses, -usage.last_used.toordinal())
