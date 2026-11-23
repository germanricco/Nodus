"""What each category added up to in a period, for the categories page.

It counts as the dashboard does (shared ``converted_movements``): transfers are left out,
dollars are converted at the rate of their day, a refund is less spending in the category
of the expense it pays back, and what lacks a rate is counted apart.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from nodus.models.category import Category
from nodus.models.currency import HOME_CURRENCY
from nodus.models.money import Money
from nodus.models.period import Period
from nodus.models.transaction import TransactionType
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.classification.category_service import CategoryService
from nodus.services.conversion import ConvertedMovement, converted_movements, period_filter
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

    def report(self, period: Period) -> CategoryReport:
        converted = converted_movements(
            self._transactions, self._exchange_rates, period_filter(period)
        )
        sections = [
            self._section(kind, converted.movements)
            for kind in (TransactionType.EXPENSE, TransactionType.INCOME)
        ]
        return CategoryReport(period, sections, converted.unconverted)

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
