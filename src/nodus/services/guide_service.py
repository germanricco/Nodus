"""Primeros pasos, the short list that walks a new user through Nodus, and when to offer
the guided tour.

Each step is worked out from the data, never stored, so the list can't fall out of
step with what the user did: creating the first account ticks «Crea tu primera
cuenta» wherever it was created from.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.account_service import AccountService
from nodus.services.budget_service import BudgetService
from nodus.services.goal_service import GoalService
from nodus.services.recurring_charge_service import RecurringChargeService
from nodus.services.settings_service import SettingsService
from nodus.services.transaction_service import TransactionService

# Someone whose data is older than this already knows their way around: the list
# would only be in the way.
NEW_USER_DAYS = 60


class GuideStepKind(StrEnum):
    ACCOUNT = "account"
    EXPENSE = "expense"
    RECURRING = "recurring"
    BUDGET = "budget"
    GOAL = "goal"
    BACKUP = "backup"


@dataclass(frozen=True)
class GuideStep:
    kind: GuideStepKind
    title: str
    done: bool


TITLES = {
    GuideStepKind.ACCOUNT: "Crea tu primera cuenta",
    GuideStepKind.EXPENSE: "Anota un gasto",
    GuideStepKind.RECURRING: "Agrega un pago recurrente",
    GuideStepKind.BUDGET: "Ponle un límite a una categoría",
    GuideStepKind.GOAL: "Ahorra para algo",
    GuideStepKind.BACKUP: "Guarda una copia fuera de la PC",
}


class GuideService:
    """Which first steps are done, and whether the list is still worth showing."""

    def __init__(
        self,
        accounts: AccountService,
        transactions: TransactionService,
        recurring: RecurringChargeService,
        budgets: BudgetService,
        goals: GoalService,
        settings: SettingsService,
    ) -> None:
        self._accounts = accounts
        self._transactions = transactions
        self._recurring = recurring
        self._budgets = budgets
        self._goals = goals
        self._settings = settings

    def steps(self, today: date) -> list[GuideStep]:
        done = {
            GuideStepKind.ACCOUNT: bool(self._accounts.list_accounts(include_archived=True)),
            GuideStepKind.EXPENSE: bool(
                self._transactions.list_transactions(
                    TransactionFilter(type=TransactionType.EXPENSE, is_transfer=False, limit=1)
                )
            ),
            GuideStepKind.RECURRING: bool(self._recurring.list_charges()),
            GuideStepKind.BUDGET: bool(self._budgets.limits_on(Month.of(today))),
            GuideStepKind.GOAL: bool(self._goals.list_goals()),
            GuideStepKind.BACKUP: self._settings.last_external_backup() is not None,
        }
        return [GuideStep(kind, TITLES[kind], done[kind]) for kind in GuideStepKind]

    def visible(self, today: date) -> bool:
        """Shown until the user puts it away, to whoever started less than
        ``NEW_USER_DAYS`` ago, or has not started yet. Once every step is done it stays,
        saying so, until it is closed."""
        if self._settings.guide_dismissed():
            return False
        since = self._accounts.first_created_on()
        return since is None or today - since < timedelta(days=NEW_USER_DAYS)

    def dismiss(self) -> None:
        self._settings.set_guide_dismissed(True)

    def tour_due(self) -> bool:
        """Whether to offer the guided tour now: once, to whoever has an account. A new
        user gets it right after the first one; someone updating, the first time they
        open this version (after its news)."""
        has_accounts = bool(self._accounts.list_accounts(include_archived=True))
        return has_accounts and not self._settings.tour_offered()

    def mark_tour_offered(self) -> None:
        self._settings.set_tour_offered(True)

    def restore(self) -> None:
        """Brings the list back, from Ayuda; it still waits for a new user's data."""
        self._settings.set_guide_dismissed(False)
