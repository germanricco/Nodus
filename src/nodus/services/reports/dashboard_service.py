"""Figures for the dashboard: how a period went and how it compares with the one before.

They count as ``services/conversion`` does, like the analysis; the month-by-month flow is
shared with it too.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from nodus.models.category import Category
from nodus.models.currency import HOME_CURRENCY
from nodus.models.money import Money
from nodus.models.period import RECENT_MONTHS, Month, Period
from nodus.models.transaction import Transaction, TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.classification.category_service import CategoryService
from nodus.services.conversion import (
    ConvertedMovement,
    ConvertedMovements,
    FlowFigures,
    convert_movements,
    converted_movements,
    flow_totals,
    period_filter,
    positive_totals,
    relative_change,
)
from nodus.services.transactions.transaction_service import TransactionService


@dataclass(frozen=True)
class FilteredTotals(FlowFigures):
    """Income and expenses in pesos of the movements a filter shows, for the foot of the
    transactions list. Refunds count as less spending, as everywhere else."""

    income: Money
    expenses: Money
    unconverted: int

    @property
    def net(self) -> Money:
        return self.savings


@dataclass(frozen=True)
class CategoryTotal:
    """What was spent in a top-level category, its subcategories included, and in how
    many movements (counted only where they are shown, as in Análisis)."""

    category: Category
    total: Money
    count: int = 0


@dataclass(frozen=True)
class PeriodSummary(FlowFigures):
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
class MonthFlow(FlowFigures):
    """Income and expenses of one month, a bar of the cash flow chart."""

    month: Month
    income: Money
    expenses: Money


def month_flows(movements: list[ConvertedMovement], months: list[Month]) -> list[MonthFlow]:
    """Income and expenses of each of ``months``, from movements already in pesos."""
    by_month: dict[Month, list[ConvertedMovement]] = {month: [] for month in months}
    for movement in movements:
        by_month.get(Month.of(movement.transaction.occurred_on), []).append(movement)
    flows = [(month, flow_totals(by_month[month])) for month in months]
    return [MonthFlow(month, totals.income, totals.expenses) for month, totals in flows]


class DashboardService:
    """The figures of Inicio for a period, and the same for the period before to compare."""

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
        by_category: dict[int, Money] = defaultdict(lambda: Money.zero(HOME_CURRENCY))
        converted = self._converted(period)
        for movement in converted.movements:
            if movement.kind is TransactionType.EXPENSE:
                category = categories[movement.category_id]
                by_category[category.parent_id or category.id] += movement.amount
        ranked = positive_totals(by_category)
        totals = flow_totals(converted.movements)
        return PeriodSummary(
            period=period,
            income=totals.income,
            expenses=totals.expenses,
            expenses_by_category=[CategoryTotal(categories[i], total) for i, total in ranked],
            unconverted=converted.unconverted,
        )

    def comparison(self, period: Period) -> Comparison:
        current = self.summary(period)
        previous = self.summary(period.previous())
        before = {t.category.id: t.total for t in previous.expenses_by_category}
        zero = Money.zero(HOME_CURRENCY)
        changes = [
            CategoryChange(t.category, t.total, before.get(t.category.id, zero))
            for t in current.expenses_by_category
        ]
        return Comparison(current, previous, changes)

    def monthly_flow(self, period: Period) -> list[MonthFlow]:
        """Income and expenses of each month of ``period``; for a single month, of the
        ``RECENT_MONTHS`` months that end with it, a year to see the trend in, as in
        Análisis and on a record's page."""
        months = period.months()
        if len(months) == 1:
            months = [months[0].shifted(-i) for i in reversed(range(RECENT_MONTHS))]
        converted = self._converted(Period.of_months(months[0], months[-1]))
        return month_flows(converted.movements, months)

    def totals(self, criteria: TransactionFilter) -> FilteredTotals:
        """What the movements matching ``criteria`` add up to, transfers aside."""
        return self._totals(converted_movements(self._transactions, self._exchange_rates, criteria))

    def totals_of(self, transactions: list[Transaction]) -> FilteredTotals:
        """What ``transactions`` add up to, transfers aside, as for a selection."""
        return self._totals(
            convert_movements(self._transactions, self._exchange_rates, transactions)
        )

    def _totals(self, converted: ConvertedMovements) -> FilteredTotals:
        totals = flow_totals(converted.movements)
        return FilteredTotals(totals.income, totals.expenses, converted.unconverted)

    def _converted(self, period: Period) -> ConvertedMovements:
        return converted_movements(self._transactions, self._exchange_rates, period_filter(period))
