"""Business rules for payees: unique names, merging and what each one adds up to."""

from __future__ import annotations

import dataclasses
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.payee_repository import PayeeRepository
from nodus.models.category import Category
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.payee import Payee, normalize_name
from nodus.models.transaction import Transaction, TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.category_service import CategoryService
from nodus.services.dashboard_service import net_in_pesos
from nodus.services.errors import ValidationError, clean_name, require_found
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.sorting import name_sort_key, rank_matches
from nodus.services.transaction_service import TransactionService


@dataclass(frozen=True)
class PayeeSummary:
    """A payee with its transactions added up, for the payees page.

    ``net`` is income minus expenses in pesos, with dollars converted at the rate of their
    day; those without a rate yet are left out and counted in ``unconverted``.
    ``top_category`` is the one used most with this payee, and ``first_on`` and
    ``last_on`` the dates of its first and latest transactions (None while it has none).
    """

    payee: Payee
    count: int
    net: Money
    unconverted: int
    top_category: Category | None
    first_on: date | None
    last_on: date | None


class PayeeService:
    CURRENCY = Currency.ARS

    def __init__(
        self,
        database: Database,
        payees: PayeeRepository,
        transactions: TransactionService,
        categories: CategoryService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._database = database
        self._payees = payees
        self._transactions = transactions
        self._categories = categories
        self._exchange_rates = exchange_rates

    def list_payees(self) -> list[Payee]:
        """Every payee in alphabetical order."""
        return sorted(self._payees.list(), key=lambda p: name_sort_key(p.name))

    def get(self, payee_id: int) -> Payee:
        return require_found(self._payees.get(payee_id), "El beneficiario no existe.")

    def find(self, name: str) -> Payee | None:
        """The payee called ``name``, ignoring case, accents and signs."""
        normalized = normalize_name(name)
        return self._payees.find_by_normalized(normalized) if normalized else None

    def matches(self, text: str) -> list[Payee]:
        """Payees whose name contains ``text``, those starting with it first."""
        return rank_matches(self._payees.list(), text)

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

    def delete(self, payee_id: int) -> int:
        """Deletes a payee and returns how many transactions were left without one."""
        self.get(payee_id)
        count = self._payees.count_transactions(payee_id)
        with self._database.transaction():
            self._payees.delete(payee_id)
        return count

    def merge(self, source_id: int, target_id: int) -> None:
        """Moves the transactions of ``source_id`` to ``target_id`` and deletes the former.

        The target keeps its default category, or takes the source's if it had none.
        """
        if source_id == target_id:
            raise ValidationError("Elige otro beneficiario para unir.")
        source = self.get(source_id)
        target = self.get(target_id)
        with self._database.transaction():
            self._payees.reassign(source_id, target_id)
            if target.default_category_id is None and source.default_category_id is not None:
                self._payees.update(
                    dataclasses.replace(target, default_category_id=source.default_category_id)
                )
            self._payees.delete(source_id)

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

    def summaries(self) -> list[PayeeSummary]:
        """Every payee with its totals, the most used first."""
        by_payee: dict[int, list[Transaction]] = defaultdict(list)
        for transaction in self._transactions.list_transactions(
            TransactionFilter(is_transfer=False)
        ):
            if transaction.payee_id is not None:
                by_payee[transaction.payee_id].append(transaction)
        categories = {c.id: c for c in self._categories.list_categories()}
        summaries = [self._summary(p, by_payee[p.id], categories) for p in self._payees.list()]
        return sorted(summaries, key=lambda s: (-s.count, name_sort_key(s.payee.name)))

    def _summary(
        self, payee: Payee, transactions: list[Transaction], categories: dict[int, Category]
    ) -> PayeeSummary:
        net, unconverted = net_in_pesos(transactions, self._exchange_rates)
        usage = Counter(t.category_id for t in transactions).most_common(1)
        return PayeeSummary(
            payee=payee,
            count=len(transactions),
            net=net,
            unconverted=unconverted,
            top_category=categories[usage[0][0]] if usage else None,
            first_on=min((t.occurred_on for t in transactions), default=None),
            last_on=max((t.occurred_on for t in transactions), default=None),
        )

    def _checked(self, payee: Payee) -> Payee:
        """``payee`` if its name is usable and no other payee has it."""
        if not payee.normalized_name:
            raise ValidationError("El nombre debe tener letras o números.")
        if payee.default_category_id is not None:
            self._categories.get(payee.default_category_id)
        existing = self._payees.find_by_normalized(payee.normalized_name)
        if existing is not None and existing.id != payee.id:
            hint = "; para juntarlos usa «Unir con…»" if payee.id is not None else ""
            raise ValidationError(f"Ya existe «{existing.name}»{hint}.")
        return payee
