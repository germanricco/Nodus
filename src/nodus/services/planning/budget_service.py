"""Business rules for budgets: monthly limits per expense category and how each month
is going against them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.budget_repository import BudgetRepository
from nodus.i18n import _
from nodus.models.budget import Budget, BudgetState, MonthLimit, days_left, month_elapsed
from nodus.models.category import Category
from nodus.models.currency import HOME_CURRENCY
from nodus.models.money import Money
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.classification.category_service import CategoryService
from nodus.services.errors import ValidationError, require_storable
from nodus.services.reports.dashboard_service import CategoryTotal, DashboardService
from nodus.services.transactions.transaction_service import TransactionService

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
    categories without a limit, the largest first. ``unconverted`` counts expenses in another
    currency left out for lack of an exchange rate, as on the dashboard. ``days_left``
    counts the days still to spend in, today included (``models.budget.days_left``).
    """

    month: Month
    budgets: list[Budget]
    unbudgeted: list[CategoryTotal]
    unconverted: int
    elapsed: float
    days_left: int

    @property
    def total(self) -> MonthLimit:
        """All the budgets together: what the page's question («how much can I still
        spend?») is answered from."""
        zero = Money.zero(HOME_CURRENCY)
        limit = sum((b.limit for b in self.budgets), zero)
        spent = sum((b.spent for b in self.budgets), zero)
        return MonthLimit(limit, spent, self.elapsed)

    @property
    def limit(self) -> Money:
        return self.total.limit

    @property
    def spent(self) -> Money:
        return self.total.spent

    @property
    def remaining(self) -> Money:
        return self.total.remaining

    @property
    def per_day(self) -> Money | None:
        """What is left split over the days to go, rounded down so that spending it
        every day never passes the limit; None when nothing is left or no day is."""
        remaining = self.remaining
        if self.days_left == 0 or remaining.cents <= 0:
            return None
        return Money(remaining.cents // self.days_left, remaining.currency)

    @property
    def over(self) -> list[Budget]:
        """The budgets passed, the most used first."""
        return [b for b in self.budgets if b.state is BudgetState.OVER]

    @property
    def unbudgeted_spent(self) -> Money:
        """All that was spent in categories without a limit, which the limits do not see."""
        return sum((t.total for t in self.unbudgeted), Money.zero(HOME_CURRENCY))


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
        if amount.currency is not HOME_CURRENCY:
            raise ValidationError(_("El límite del presupuesto va en pesos."), field="limit")
        if amount.cents <= 0:
            raise ValidationError(_("El límite tiene que ser mayor que cero."), field="limit")
        require_storable(amount, "limit")
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
        """The limit of each category in ``month``, by category id."""
        return self._budgets.limits_on(month)

    def month_budgets(self, month: Month, today: date) -> MonthBudgets:
        """Each budgeted category's limit against what it spent in ``month``, and what was
        spent in categories without one."""
        summary = self._dashboard.summary(Period.of_months(month))
        spent = {t.category.id: t.total for t in summary.expenses_by_category}
        limits = self._budgets.limits_on(month)
        categories = {c.id: c for c in self._categories.list_categories(TransactionType.EXPENSE)}
        elapsed = month_elapsed(month, today)
        zero = Money.zero(HOME_CURRENCY)
        budgets = sorted(
            (
                Budget(categories[i], limit, spent.get(i, zero), elapsed)
                for i, limit in limits.items()
            ),
            key=lambda b: (-b.used, b.category.name.casefold()),
        )
        unbudgeted = [t for t in summary.expenses_by_category if t.category.id not in limits]
        return MonthBudgets(
            month, budgets, unbudgeted, summary.unconverted, elapsed, days_left(month, today)
        )

    def over_limit(self, today: date) -> list[Budget]:
        """The budgets already passed in the current month."""
        return self.month_budgets(Month.of(today), today).over

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
        return BudgetSuggestion(Money(rounded, HOME_CURRENCY), len(months))

    def _require_budgetable(self, category_id: int) -> Category:
        category = self._categories.get(category_id)
        if category.kind is not TransactionType.EXPENSE:
            raise ValidationError(_("Solo las categorías de gasto llevan presupuesto."))
        if category.is_subcategory:
            raise ValidationError(
                _("Los presupuestos van en la categoría principal; sus subcategorías suman a ella.")
            )
        return category
