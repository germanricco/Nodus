"""Figures for the dashboard: how a month went."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.category import Category
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.category_service import CategoryService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.transaction_service import TransactionService


@dataclass(frozen=True)
class CategoryTotal:
    """What was spent in a top-level category, its subcategories included."""

    category: Category
    total: Money


@dataclass(frozen=True)
class MonthSummary:
    """Income and expenses of a month, in pesos.

    Dollar movements are converted at the rate of their day. Those without a rate yet
    cannot be converted: they are left out and counted in ``unconverted``, so the screen
    can say so instead of showing a wrong total. Transfers are not income or expenses.
    """

    month: Month
    income: Money
    expenses: Money
    expenses_by_category: list[CategoryTotal]  # largest first
    unconverted: int

    @property
    def savings(self) -> Money:
        return self.income - self.expenses


class DashboardService:
    CURRENCY = Currency.ARS

    def __init__(
        self,
        transactions: TransactionService,
        categories: CategoryService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._transactions = transactions
        self._categories = categories
        self._exchange_rates = exchange_rates

    def month_summary(self, month: Month) -> MonthSummary:
        movements = self._transactions.list_transactions(
            TransactionFilter(start=month.start, end=month.end, is_transfer=False)
        )
        categories = {c.id: c for c in self._categories.list_categories()}
        totals = {kind: Money.zero(self.CURRENCY) for kind in TransactionType}
        by_category: dict[int, Money] = defaultdict(lambda: Money.zero(self.CURRENCY))
        unconverted = 0
        for transaction in movements:
            amount = self._in_summary_currency(transaction)
            if amount is None:
                unconverted += 1
                continue
            totals[transaction.type] += amount
            if transaction.type is TransactionType.EXPENSE:
                category = categories[transaction.category_id]
                by_category[category.parent_id or category.id] += amount
        ranked = sorted(by_category.items(), key=lambda item: item[1].cents, reverse=True)
        return MonthSummary(
            month=month,
            income=totals[TransactionType.INCOME],
            expenses=totals[TransactionType.EXPENSE],
            expenses_by_category=[CategoryTotal(categories[i], total) for i, total in ranked],
            unconverted=unconverted,
        )

    def _in_summary_currency(self, transaction: Transaction) -> Money | None:
        return self._exchange_rates.convert(
            transaction.amount, self.CURRENCY, transaction.occurred_on
        )
