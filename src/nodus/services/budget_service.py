"""Business rules for budgets: monthly limits per expense category and how each month
is going against them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.budget_repository import BudgetRepository
from nodus.models.budget import Budget, BudgetState, month_elapsed
from nodus.models.category import Category
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.category_service import CategoryService
from nodus.services.dashboard_service import CategoryTotal, DashboardService
from nodus.services.errors import ValidationError
from nodus.services.transaction_service import TransactionService

# Budgets are kept in pesos, the currency of the dashboard's totals.
CURRENCY = Currency.ARS
# The limit suggested for a new budget is the average spending of this many months before.
SUGGESTION_MONTHS = 3
# Suggestions are rounded to whole thousands of pesos (in cents), as people set limits.
SUGGESTION_ROUNDING = 1000_00


@dataclass(frozen=True)
class BudgetSuggestion:
    """A limit to start from: what was spent per month in the ``months`` before, which
    may be fewer than ``SUGGESTION_MONTHS`` when Nodus has been used for less."""

    amount: Money
    months: int


@dataclass(frozen=True)
class MonthBudgets:
    """A month against its budgets.

    ``budgets`` go from the most to the least used. ``unbudgeted`` is the spending in
    categories without a limit, the largest first. ``unconverted`` counts dollar expenses
    left out for lack of an exchange rate, as on the dashboard.
    """

    month: Month
    budgets: list[Budget]
    unbudgeted: list[CategoryTotal]
    unconverted: int
    elapsed: float

    @property
    def limit(self) -> Money:
        return sum((b.limit for b in self.budgets), Money.zero(CURRENCY))

    @property
    def spent(self) -> Money:
        return sum((b.spent for b in self.budgets), Money.zero(CURRENCY))

    @property
    def remaining(self) -> Money:
        return self.limit - self.spent


class BudgetService:
    """Limits are in pesos and belong to top-level expense categories: spending in a
    subcategory counts toward its parent, as on the dashboard's ring."""

    def __init__(
        self,
        database: Database,
        budgets: BudgetRepository,
        categories: CategoryService,
        dashboard: DashboardService,
        transactions: TransactionService,
    ) -> None:
        self._database = database
        self._budgets = budgets
        self._categories = categories
        self._dashboard = dashboard
        self._transactions = transactions

    def set_limit(self, category_id: int, month: Month, amount: Money) -> None:
        """Sets the limit from ``month`` on; earlier months keep the one they had."""
        self._require_budgetable(category_id)
        if amount.currency is not CURRENCY:
            raise ValidationError("El límite del presupuesto va en pesos.", field="limit")
        if amount.cents <= 0:
            raise ValidationError("El límite tiene que ser mayor que cero.", field="limit")
        with self._database.transaction():
            self._budgets.set(category_id, month, amount)

    def remove(self, category_id: int, month: Month) -> None:
        """Ends the budget from ``month`` on, keeping the earlier months."""
        self._require_budgetable(category_id)
        with self._database.transaction():
            self._budgets.set(category_id, month, None)

    def categories(self) -> list[Category]:
        """The categories that can carry a budget, in display order."""
        return [node.category for node in self._categories.category_tree(TransactionType.EXPENSE)]

    def limits_on(self, month: Month) -> dict[int, Money]:
        return self._budgets.limits_on(month)

    def month_budgets(self, month: Month, today: date) -> MonthBudgets:
        summary = self._dashboard.summary(Period.of_months(month))
        spent = {t.category.id: t.total for t in summary.expenses_by_category}
        limits = self._budgets.limits_on(month)
        categories = {c.id: c for c in self._categories.list_categories(TransactionType.EXPENSE)}
        elapsed = month_elapsed(month, today)
        zero = Money.zero(CURRENCY)
        budgets = sorted(
            (
                Budget(categories[i], limit, spent.get(i, zero), elapsed)
                for i, limit in limits.items()
            ),
            key=lambda b: (-b.used, b.category.name.casefold()),
        )
        unbudgeted = [t for t in summary.expenses_by_category if t.category.id not in limits]
        return MonthBudgets(month, budgets, unbudgeted, summary.unconverted, elapsed)

    def over_limit(self, today: date) -> list[Budget]:
        """The budgets already passed in the current month."""
        budgets = self.month_budgets(Month.of(today), today).budgets
        return [b for b in budgets if b.state is BudgetState.OVER]

    def suggestion(self, category_id: int, month: Month) -> BudgetSuggestion | None:
        """The average spending of the ``SUGGESTION_MONTHS`` months before ``month``,
        rounded to thousands; None when nothing was spent in the category. Only the months
        with a history count, so a month of use does not suggest a third of it."""
        before = Period.of_months(month.shifted(-SUGGESTION_MONTHS), month.previous())
        months = self._transactions.history_months(before, month.previous().end)
        total = 0
        for counted in months:
            summary = self._dashboard.summary(Period.of_months(counted))
            total += sum(
                t.total.cents for t in summary.expenses_by_category if t.category.id == category_id
            )
        if total <= 0:
            return None
        average = total / len(months)
        rounded = max(1, round(average / SUGGESTION_ROUNDING)) * SUGGESTION_ROUNDING
        return BudgetSuggestion(Money(rounded, CURRENCY), len(months))

    def _require_budgetable(self, category_id: int) -> Category:
        category = self._categories.get(category_id)
        if category.kind is not TransactionType.EXPENSE:
            raise ValidationError("Solo las categorías de gasto llevan presupuesto.")
        if category.is_subcategory:
            raise ValidationError(
                "Los presupuestos van en la categoría principal; sus subcategorías suman a ella."
            )
        return category
