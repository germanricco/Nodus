"""Figures for the dashboard: how a period went and how it compares with the one before."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.category import Category
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month, Period
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.category_service import CategoryService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.transaction_service import TransactionService

# A single month shows the trend of the months leading to it.
TREND_MONTHS = 6


def relative_change(current: Money, previous: Money) -> float | None:
    """How much ``current`` moved from ``previous``, as a fraction (0.1 is +10 %).

    None when ``previous`` is zero: there is nothing to compare with.
    """
    if previous.is_zero:
        return None
    return (current.cents - previous.cents) / abs(previous.cents)


@dataclass(frozen=True)
class CategoryTotal:
    """What was spent in a top-level category, its subcategories included."""

    category: Category
    total: Money


@dataclass(frozen=True)
class PeriodSummary:
    """Income and expenses of a period, in pesos.

    Dollar movements are converted at the rate of their day. Those without a rate yet
    cannot be converted: they are left out and counted in ``unconverted``, so the screen
    can say so instead of showing a wrong total. Transfers are not income or expenses.
    """

    period: Period
    income: Money
    expenses: Money
    expenses_by_category: list[CategoryTotal]  # largest first
    unconverted: int

    @property
    def savings(self) -> Money:
        return self.income - self.expenses


@dataclass(frozen=True)
class CategoryChange:
    """A category's spending now and in the previous period."""

    category: Category
    current: Money
    previous: Money

    @property
    def change(self) -> float | None:
        """None when nothing was spent before: the category is new in this period."""
        return relative_change(self.current, self.previous)


@dataclass(frozen=True)
class Comparison:
    """A period next to the one of the same length right before it."""

    current: PeriodSummary
    previous: PeriodSummary
    categories: list[CategoryChange]  # spent in the current period, largest first

    @property
    def savings_change(self) -> float | None:
        return relative_change(self.current.savings, self.previous.savings)

    @property
    def expenses_change(self) -> float | None:
        return relative_change(self.current.expenses, self.previous.expenses)


@dataclass(frozen=True)
class MonthFlow:
    """Income and expenses of one month, a bar of the cash flow chart."""

    month: Month
    income: Money
    expenses: Money

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

    def summary(self, period: Period) -> PeriodSummary:
        categories = {c.id: c for c in self._categories.list_categories()}
        totals = {kind: Money.zero(self.CURRENCY) for kind in TransactionType}
        by_category: dict[int, Money] = defaultdict(lambda: Money.zero(self.CURRENCY))
        unconverted = 0
        for transaction in self._movements(period):
            amount = self._in_summary_currency(transaction)
            if amount is None:
                unconverted += 1
                continue
            totals[transaction.type] += amount
            if transaction.type is TransactionType.EXPENSE:
                category = categories[transaction.category_id]
                by_category[category.parent_id or category.id] += amount
        ranked = sorted(by_category.items(), key=lambda item: item[1].cents, reverse=True)
        return PeriodSummary(
            period=period,
            income=totals[TransactionType.INCOME],
            expenses=totals[TransactionType.EXPENSE],
            expenses_by_category=[CategoryTotal(categories[i], total) for i, total in ranked],
            unconverted=unconverted,
        )

    def comparison(self, period: Period) -> Comparison:
        current = self.summary(period)
        previous = self.summary(period.previous())
        before = {t.category.id: t.total for t in previous.expenses_by_category}
        zero = Money.zero(self.CURRENCY)
        changes = [
            CategoryChange(t.category, t.total, before.get(t.category.id, zero))
            for t in current.expenses_by_category
        ]
        return Comparison(current, previous, changes)

    def monthly_flow(self, period: Period) -> list[MonthFlow]:
        """Income and expenses of each month of ``period``; for a single month, of the
        ``TREND_MONTHS`` months that end with it, so there is a trend to see."""
        months = period.months()
        if len(months) == 1:
            months = [months[0].shifted(-i) for i in reversed(range(TREND_MONTHS))]
        zero = Money.zero(self.CURRENCY)
        totals = {month: {kind: zero for kind in TransactionType} for month in months}
        for transaction in self._movements(Period.of_months(months[0], months[-1])):
            amount = self._in_summary_currency(transaction)
            if amount is not None:
                totals[Month.of(transaction.occurred_on)][transaction.type] += amount
        return [
            MonthFlow(
                month, totals[month][TransactionType.INCOME], totals[month][TransactionType.EXPENSE]
            )
            for month in months
        ]

    def _movements(self, period: Period) -> list[Transaction]:
        """Income and expenses of ``period``; transfers only move money between accounts."""
        return self._transactions.list_transactions(
            TransactionFilter(start=period.start, end=period.end, is_transfer=False)
        )

    def _in_summary_currency(self, transaction: Transaction) -> Money | None:
        return self._exchange_rates.convert(
            transaction.amount, self.CURRENCY, transaction.occurred_on
        )
