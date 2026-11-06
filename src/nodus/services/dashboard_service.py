"""Figures for the dashboard: how a period went and how it compares with the one before.

The movements converted to pesos and the month-by-month flow are shared with the analysis
service, so both screens count the same way.
"""

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
SUMMARY_CURRENCY = Currency.ARS


def relative_change(current: Money, previous: Money) -> float | None:
    """How much ``current`` moved from ``previous``, as a fraction (0.1 is +10 %).

    None when ``previous`` is zero: there is nothing to compare with.
    """
    if previous.is_zero:
        return None
    return (current.cents - previous.cents) / abs(previous.cents)


def savings_rate(income: Money, expenses: Money) -> float | None:
    """The share of ``income`` that was not spent (0.2 is 20 %); None without income."""
    if income.cents <= 0:
        return None
    return (income.cents - expenses.cents) / income.cents


@dataclass(frozen=True)
class ConvertedMovement:
    """An income or expense with its amount in pesos, converted at the rate of its day.

    ``kind`` and ``category_id`` are what the movement counts as. They are the
    transaction's own, except for a refund: it counts as a negative expense in the
    category of the expense it pays back, on the day the money came back.
    """

    transaction: Transaction
    amount: Money
    kind: TransactionType
    category_id: int


@dataclass(frozen=True)
class ConvertedMovements:
    """The income and expenses of a period in pesos. Dollar movements of days without a
    rate cannot be converted: they are left out and counted in ``unconverted``, so the
    screen can say so instead of showing a wrong total."""

    movements: list[ConvertedMovement]
    unconverted: int


def converted_movements(
    transactions: TransactionService, exchange_rates: ExchangeRateService, period: Period
) -> ConvertedMovements:
    """Income and expenses of ``period`` in pesos; transfers only move money between
    accounts, so they are left out. Refunds are turned into less spending."""
    movements: list[ConvertedMovement] = []
    unconverted = 0
    refunded_categories: dict[int, int] = {}
    for transaction in transactions.list_transactions(
        TransactionFilter(start=period.start, end=period.end, is_transfer=False)
    ):
        amount = exchange_rates.convert(
            transaction.amount, SUMMARY_CURRENCY, transaction.occurred_on
        )
        if amount is None:
            unconverted += 1
        elif transaction.refund_of_id is None:
            movements.append(
                ConvertedMovement(transaction, amount, transaction.type, transaction.category_id)
            )
        else:
            expense_id = transaction.refund_of_id
            if expense_id not in refunded_categories:
                refunded_categories[expense_id] = transactions.get(expense_id).category_id
            movements.append(
                ConvertedMovement(
                    transaction, -amount, TransactionType.EXPENSE, refunded_categories[expense_id]
                )
            )
    return ConvertedMovements(movements, unconverted)


def net_in_pesos(
    transactions: list[Transaction], exchange_rates: ExchangeRateService
) -> tuple[Money, int]:
    """Income minus expenses of ``transactions`` in pesos, each at the rate of its day, and
    how many could not be converted for lack of a rate."""
    net = Money.zero(SUMMARY_CURRENCY)
    unconverted = 0
    for transaction in transactions:
        amount = exchange_rates.convert(
            transaction.signed_amount, SUMMARY_CURRENCY, transaction.occurred_on
        )
        if amount is None:
            unconverted += 1
        else:
            net += amount
    return net, unconverted


def positive_totals(totals: dict[int, Money]) -> list[tuple[int, Money]]:
    """The ``totals`` above zero, largest first. A category whose refunds outweigh its
    spending in a period has nothing to show for it."""
    kept = [(key, total) for key, total in totals.items() if total.cents > 0]
    return sorted(kept, key=lambda item: item[1].cents, reverse=True)


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

    @property
    def savings_rate(self) -> float | None:
        return savings_rate(self.income, self.expenses)


def month_flows(movements: list[ConvertedMovement], months: list[Month]) -> list[MonthFlow]:
    """Income and expenses of each of ``months``, from movements already in pesos."""
    zero = Money.zero(SUMMARY_CURRENCY)
    totals = {month: {kind: zero for kind in TransactionType} for month in months}
    for movement in movements:
        month = Month.of(movement.transaction.occurred_on)
        if month in totals:
            totals[month][movement.kind] += movement.amount
    return [
        MonthFlow(
            month, totals[month][TransactionType.INCOME], totals[month][TransactionType.EXPENSE]
        )
        for month in months
    ]


class DashboardService:
    CURRENCY = SUMMARY_CURRENCY

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
        converted = self._converted(period)
        for movement in converted.movements:
            totals[movement.kind] += movement.amount
            if movement.kind is TransactionType.EXPENSE:
                category = categories[movement.category_id]
                by_category[category.parent_id or category.id] += movement.amount
        ranked = positive_totals(by_category)
        return PeriodSummary(
            period=period,
            income=totals[TransactionType.INCOME],
            expenses=totals[TransactionType.EXPENSE],
            expenses_by_category=[CategoryTotal(categories[i], total) for i, total in ranked],
            unconverted=converted.unconverted,
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
        converted = self._converted(Period.of_months(months[0], months[-1]))
        return month_flows(converted.movements, months)

    def _converted(self, period: Period) -> ConvertedMovements:
        return converted_movements(self._transactions, self._exchange_rates, period)
