"""What each category added up to: in a period, for the categories page, and over its
history, for its own page.

It counts as the dashboard does (shared ``converted_movements``): transfers are left out,
dollars are converted at the rate of their day, a refund is less spending in the category
of the expense it pays back, and what lacks a rate is counted apart.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from nodus.models.category import Category
from nodus.models.currency import HOME_CURRENCY
from nodus.models.money import Money
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.classification.category_service import CategoryService
from nodus.services.conversion import (
    ConvertedMovement,
    convert_movements,
    converted_movements,
    period_filter,
)
from nodus.services.transactions.transaction_service import TransactionService


@dataclass(frozen=True)
class CategoryFigures:
    """A category in a period: what it added up to in pesos and in how many movements.

    A top-level category adds up its subcategories too, which come in ``children``.
    ``share`` is its part of the total of its kind (0.25 is a quarter), None while that
    total is not above zero.
    """

    category: Category
    total: Money
    count: int
    share: float | None
    children: tuple[CategoryFigures, ...] = ()


@dataclass(frozen=True)
class CategorySection:
    """The categories of one kind, the largest first, with what they add up to."""

    kind: TransactionType
    total: Money
    categories: list[CategoryFigures]


@dataclass(frozen=True)
class CategoryReport:
    """Expenses then income of ``period``; ``unconverted`` counts the movements left out
    for lack of an exchange rate."""

    period: Period
    sections: list[CategorySection]
    unconverted: int


@dataclass(frozen=True)
class CategorySummary:
    """A category over its whole history, for its own page; a top-level one adds up its
    subcategories, listed in ``children``.

    Amounts are what was spent (or received) in pesos, so they read as the list of
    categories does: ``net`` over the whole history, ``this_month`` in the current month,
    ``average`` per month over the months of ``months`` since its first movement, and
    ``months`` the last ``HISTORY_MONTHS`` months, oldest first. ``count`` is how many of
    its own movements there are; ``unconverted`` those left out for lack of a rate.
    """

    category: Category
    count: int
    net: Money
    unconverted: int
    first_on: date | None
    last_on: date | None
    this_month: Money
    average: Money | None
    months: list[tuple[Month, Money]]
    children: list[Category]


class CategoryReportService:
    """Every category with what it added up to in a period, as a tree of parents and
    subcategories."""

    def __init__(
        self,
        categories: CategoryService,
        transactions: TransactionService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._categories = categories
        self._transactions = transactions
        self._exchange_rates = exchange_rates

    HISTORY_MONTHS = 12

    def report(self, period: Period) -> CategoryReport:
        converted = converted_movements(
            self._transactions, self._exchange_rates, period_filter(period)
        )
        sections = [
            self._section(kind, converted.movements)
            for kind in (TransactionType.EXPENSE, TransactionType.INCOME)
        ]
        return CategoryReport(period, sections, converted.unconverted)

    def summary(self, category_id: int, today: date) -> CategorySummary:
        """``category_id`` with its subcategories, over its whole history; NotFoundError
        once it was deleted or merged."""
        category = self._categories.get(category_id)
        children = next(
            (n.children for n in self._categories.category_tree(category.kind)
             if n.category.id == category_id),
            [],
        )  # fmt: skip
        ids = {category_id, *(child.id for child in children)}
        own = self._transactions.list_transactions(TransactionFilter(category_id=category_id))
        # A refund counts against the expense it pays back, which may be in this category.
        everything = convert_movements(
            self._transactions,
            self._exchange_rates,
            self._transactions.list_transactions(TransactionFilter(is_transfer=False)),
        )
        mine = [m for m in everything.movements if m.category_id in ids and m.kind is category.kind]
        unconverted = convert_movements(self._transactions, self._exchange_rates, own).unconverted
        first_on = min((t.occurred_on for t in own), default=None)
        window = Period.last_months(self.HISTORY_MONTHS, today)
        by_month: dict[Month, Money] = defaultdict(lambda: Money.zero(HOME_CURRENCY))
        for movement in mine:
            by_month[Month.of(movement.transaction.occurred_on)] += movement.amount
        counted = window.months_since(first_on, today) if first_on else []
        average = (
            Money(round(_sum(by_month[m] for m in counted).cents / len(counted)), HOME_CURRENCY)
            if counted
            else None
        )
        return CategorySummary(
            category=category,
            count=len(own),
            net=_sum(m.amount for m in mine),
            unconverted=unconverted,
            first_on=first_on,
            last_on=max((t.occurred_on for t in own), default=None),
            this_month=by_month[Month.of(today)],
            average=average,
            months=[(month, by_month[month]) for month in window.months()],
            children=list(children),
        )

    def _section(
        self,
        kind: TransactionType,
        movements: list[ConvertedMovement],
    ) -> CategorySection:
        totals: dict[int, Money] = defaultdict(lambda: Money.zero(HOME_CURRENCY))
        counts: Counter[int] = Counter()
        for movement in movements:
            if movement.kind is kind:
                totals[movement.category_id] += movement.amount
                counts[movement.category_id] += 1
        nodes = self._categories.category_tree(kind)
        kind_total = sum(totals.values(), Money.zero(HOME_CURRENCY))

        def figures(
            category: Category,
            total: Money,
            count: int,
            children: tuple[CategoryFigures, ...] = (),
        ) -> CategoryFigures:
            share = total.cents / kind_total.cents if kind_total.cents > 0 else None
            return CategoryFigures(category, total, count, share, children)

        parents = []
        for node in nodes:
            children = tuple(
                _largest_first(
                    figures(child, totals[child.id], counts[child.id]) for child in node.children
                )
            )
            total = totals[node.category.id] + sum(
                (child.total for child in children), Money.zero(HOME_CURRENCY)
            )
            count = counts[node.category.id] + sum(child.count for child in children)
            parents.append(figures(node.category, total, count, children))
        return CategorySection(kind, kind_total, _largest_first(parents))


def _largest_first(figures: Iterable[CategoryFigures]) -> list[CategoryFigures]:
    """The largest totals first; those without movements last, in the order they came in
    (the list of categories: alphabetical, «Otros» at the end)."""
    return sorted(figures, key=lambda f: (f.count == 0, -f.total.cents if f.count else 0))


def _sum(amounts: Iterable[Money]) -> Money:
    return sum(amounts, Money.zero(HOME_CURRENCY))
