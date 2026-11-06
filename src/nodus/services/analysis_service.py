"""Figures for the analysis page: long trends of spending, income and savings.

They count the same way as the dashboard (shared ``converted_movements``): transfers are
left out, dollars are converted at the rate of their day and those without a rate are
counted apart. The net worth trend comes from ``NetWorthService.history``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from nodus.models.category import Category
from nodus.models.money import Money
from nodus.models.payee import Payee
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.category_service import CategoryService
from nodus.services.dashboard_service import (
    SUMMARY_CURRENCY,
    CategoryTotal,
    ConvertedMovement,
    MonthFlow,
    converted_movements,
    month_flows,
    relative_change,
    savings_rate,
)
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.payee_service import PayeeService
from nodus.services.transaction_service import TransactionService


class Metric(Enum):
    """What the trends report adds up, with its Spanish name."""

    EXPENSES = "Gastos"
    INCOME = "Ingresos"
    SAVINGS = "Ahorro"

    @property
    def kind(self) -> TransactionType | None:
        """The movements it adds up; None for savings, which nets both."""
        return {
            Metric.EXPENSES: TransactionType.EXPENSE,
            Metric.INCOME: TransactionType.INCOME,
        }.get(self)


@dataclass(frozen=True)
class MonthTrend:
    """One month of the trend: its total and, except for savings, its split by top-level
    category, largest first."""

    month: Month
    total: Money
    by_category: list[CategoryTotal]


@dataclass(frozen=True)
class PayeeTotal:
    """What went to (or came from) a payee; ``payee`` is None for movements without one."""

    payee: Payee | None
    total: Money
    count: int


@dataclass(frozen=True)
class Trends:
    """A metric month by month along a period, against the period of the same length right
    before it. ``categories`` and ``payees`` are empty for savings."""

    metric: Metric
    period: Period
    months: list[MonthTrend]
    total: Money
    previous_total: Money
    categories: list[CategoryTotal]  # largest first
    payees: list[PayeeTotal]  # largest first, "without payee" last
    unconverted: int

    @property
    def change(self) -> float | None:
        return relative_change(self.total, self.previous_total)

    @property
    def average(self) -> Money:
        """The monthly average along the period."""
        count = max(len(self.months), 1)
        return Money(round(self.total.cents / count), SUMMARY_CURRENCY)


@dataclass(frozen=True)
class FlowTotals:
    """Income and expenses added up over a period."""

    income: Money
    expenses: Money

    @property
    def savings(self) -> Money:
        return self.income - self.expenses

    @property
    def savings_rate(self) -> float | None:
        return savings_rate(self.income, self.expenses)


@dataclass(frozen=True)
class CashFlowReport:
    """Income, expenses and savings of each month of a period, with the totals of the
    period and of the one before it."""

    period: Period
    months: list[MonthFlow]
    current: FlowTotals
    previous: FlowTotals
    unconverted: int


def _sum(amounts) -> Money:
    return sum(amounts, Money.zero(SUMMARY_CURRENCY))


def _ranked(totals: dict) -> list:
    return sorted(totals.items(), key=lambda item: item[1].cents, reverse=True)


class AnalysisService:
    def __init__(
        self,
        transactions: TransactionService,
        categories: CategoryService,
        payees: PayeeService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._transactions = transactions
        self._categories = categories
        self._payees = payees
        self._exchange_rates = exchange_rates

    def trends(self, period: Period, metric: Metric) -> Trends:
        converted = self._converted(period)
        movements = converted.movements
        months = period.months()
        previous = self._converted(period.previous()).movements
        if metric is Metric.SAVINGS:
            month_totals = [
                MonthTrend(flow.month, flow.savings, []) for flow in month_flows(movements, months)
            ]
            return Trends(
                metric, period, month_totals, _sum(m.total for m in month_totals),
                _savings(previous), [], [], converted.unconverted,
            )  # fmt: skip
        kind = metric.kind
        chosen = [m for m in movements if m.transaction.type is kind]
        categories = {c.id: c for c in self._categories.list_categories()}
        return Trends(
            metric=metric,
            period=period,
            months=[self._month_trend(month, chosen, categories) for month in months],
            total=_sum(m.amount for m in chosen),
            previous_total=_sum(m.amount for m in previous if m.transaction.type is kind),
            categories=self._by_category(chosen, categories),
            payees=self._by_payee(chosen),
            unconverted=converted.unconverted,
        )

    def cash_flow(self, period: Period) -> CashFlowReport:
        converted = self._converted(period)
        previous = self._converted(period.previous()).movements
        return CashFlowReport(
            period=period,
            months=month_flows(converted.movements, period.months()),
            current=_flow_totals(converted.movements),
            previous=_flow_totals(previous),
            unconverted=converted.unconverted,
        )

    def _converted(self, period: Period):
        return converted_movements(self._transactions, self._exchange_rates, period)

    def _month_trend(
        self, month: Month, movements: list[ConvertedMovement], categories: dict[int, Category]
    ) -> MonthTrend:
        in_month = [m for m in movements if Month.of(m.transaction.occurred_on) == month]
        return MonthTrend(
            month, _sum(m.amount for m in in_month), self._by_category(in_month, categories)
        )

    @staticmethod
    def _by_category(
        movements: list[ConvertedMovement], categories: dict[int, Category]
    ) -> list[CategoryTotal]:
        """Totals by top-level category, subcategories included, largest first."""
        totals: dict[int, Money] = defaultdict(lambda: Money.zero(SUMMARY_CURRENCY))
        for movement in movements:
            category = categories[movement.transaction.category_id]
            totals[category.parent_id or category.id] += movement.amount
        return [CategoryTotal(categories[i], total) for i, total in _ranked(totals)]

    def _by_payee(self, movements: list[ConvertedMovement]) -> list[PayeeTotal]:
        payees = {p.id: p for p in self._payees.list_payees()}
        totals: dict[int | None, Money] = defaultdict(lambda: Money.zero(SUMMARY_CURRENCY))
        counts: dict[int | None, int] = defaultdict(int)
        for movement in movements:
            totals[movement.transaction.payee_id] += movement.amount
            counts[movement.transaction.payee_id] += 1
        ranked = [
            PayeeTotal(payees[payee_id], total, counts[payee_id])
            for payee_id, total in _ranked(totals)
            if payee_id is not None
        ]
        if None in totals:
            ranked.append(PayeeTotal(None, totals[None], counts[None]))
        return ranked


def _flow_totals(movements: list[ConvertedMovement]) -> FlowTotals:
    def total(kind: TransactionType) -> Money:
        return _sum(m.amount for m in movements if m.transaction.type is kind)

    return FlowTotals(total(TransactionType.INCOME), total(TransactionType.EXPENSE))


def _savings(movements: list[ConvertedMovement]) -> Money:
    return _flow_totals(movements).savings
