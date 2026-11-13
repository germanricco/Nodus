"""Business rules for savings goals: what each one has saved, from the balances of its
accounts, whether the user's pace reaches it in time, and when it was reached."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.goal_repository import GoalRepository
from nodus.models.account import Account, AccountType
from nodus.models.goal import PACE_CHANGES, Goal, GoalProgress, GoalShare, goal_progress
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.services.account_service import AccountService
from nodus.services.errors import ValidationError, clean_name, require_found
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.sorting import name_sort_key


@dataclass(frozen=True)
class GoalDraft:
    """What the goal form sends: the goal without its id or its history."""

    name: str
    target: Money
    target_date: date | None
    shares: tuple[GoalShare, ...]


@dataclass(frozen=True)
class GoalContribution:
    """An account of a goal: its share, its balance and what it adds to the goal, in the
    goal's currency (None without a rate)."""

    account: Account
    percent: int
    balance: Money
    counted: Money | None


class GoalService:
    """Goals are a way of looking at balances that already exist: they never move money
    and nothing is entered by hand. An account can serve several goals, a share of it
    each, as long as the shares of the goals in progress add up to 100 % at most.

    Amounts in other currencies count at today's rate, also in the past months that set
    the pace, so the pace measures what the user saved and not how the rate moved.
    """

    def __init__(
        self,
        database: Database,
        goals: GoalRepository,
        accounts: AccountService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._database = database
        self._goals = goals
        self._accounts = accounts
        self._exchange_rates = exchange_rates

    # Goals

    def list_goals(self) -> list[Goal]:
        """Every goal, archived included, in the order they were created."""
        return sorted(self._goals.list(), key=lambda g: (g.position, name_sort_key(g.name)))

    def get(self, goal_id: int) -> Goal:
        return require_found(self._goals.get(goal_id), "La meta no existe.")

    def create(self, draft: GoalDraft, today: date) -> Goal:
        goal = self._checked(draft, None, today)
        with self._database.transaction():
            position = self._goals.next_position()
            return self._goals.add(dataclasses.replace(goal, position=position))

    def update(self, goal_id: int, draft: GoalDraft, today: date) -> None:
        """Edits a goal. A new target or currency is a new goal to reach: a reached one
        goes back to being in progress, and is announced again when reached."""
        existing = self.get(goal_id)
        goal = dataclasses.replace(
            self._checked(draft, goal_id, today),
            id=goal_id,
            reached_on=existing.reached_on,
            reached_seen=existing.reached_seen,
            is_archived=existing.is_archived,
            position=existing.position,
        )
        if goal.target != existing.target:
            goal = dataclasses.replace(goal, reached_on=None, reached_seen=False)
        with self._database.transaction():
            self._goals.update(goal)

    def set_archived(self, goal_id: int, archived: bool) -> None:
        """An archived goal frees its share of each account; bringing it back takes it
        again, if the account still has it free."""
        goal = self.get(goal_id)
        if not archived:
            for share in goal.shares:
                self._check_share(share, goal_id)
        with self._database.transaction():
            self._goals.update(dataclasses.replace(goal, is_archived=archived))

    def delete(self, goal_id: int) -> None:
        """Deletes the goal; its accounts and their movements stay as they are."""
        self.get(goal_id)
        with self._database.transaction():
            self._goals.delete(goal_id)

    # Accounts

    def eligible_accounts(self) -> list[Account]:
        """The accounts a goal can count: active ones that hold money, not cards."""
        return [
            account
            for account in self._accounts.list_accounts()
            if account.type is not AccountType.CREDIT_CARD
        ]

    def free_percent(self, account_id: int, goal_id: int | None = None) -> int:
        """How much of the account the goals in progress leave free, besides ``goal_id``."""
        return 100 - sum(goal.share_of(account_id) for goal in self._others(goal_id))

    def goals_for_account(self, account_id: int) -> list[tuple[Goal, int]]:
        """The goals in progress the account adds to, with its share of each."""
        return [
            (goal, goal.share_of(account_id))
            for goal in self.list_goals()
            if not goal.is_archived and goal.share_of(account_id)
        ]

    # Progress

    def progress(self, goal: Goal, today: date) -> GoalProgress:
        month_ends = [saved for _day, saved in self.month_ends(goal, today, PACE_CHANGES + 1)]
        return goal_progress(goal, self.saved_on(goal, today, today), month_ends, today)

    def saved_on(self, goal: Goal, day: date, today: date) -> Money | None:
        """What the goal had at the end of ``day``, at today's rates; None without one."""
        balances = self._accounts.balances(day)
        total = Money.zero(goal.currency)
        for contribution in self._counted(goal, balances, today):
            if contribution is None:
                return None
            total += contribution
        return total

    def month_ends(self, goal: Goal, today: date, count: int) -> list[tuple[date, Money]]:
        """What the goal had at the end of each of the last ``count`` months, oldest first,
        from the month its accounts have data for; empty without a rate."""
        since = self._data_since(goal)
        if since is None:
            return []
        ends = []
        month = Month.of(today).previous()
        while len(ends) < count and month.end >= since:
            ends.append(month.end)
            month = month.previous()
        points = []
        for day in reversed(ends):
            saved = self.saved_on(goal, day, today)
            if saved is None:
                return []
            points.append((day, saved))
        return points

    def contributions(self, goal: Goal, today: date) -> list[GoalContribution]:
        """Each account of the goal with what it adds to it today."""
        balances = self._accounts.balances(today)
        accounts = {a.id: a for a in self._accounts.list_accounts(include_archived=True)}
        counted = self._counted(goal, balances, today)
        return [
            GoalContribution(
                accounts[share.account_id], share.percent, balances[share.account_id], amount
            )
            for share, amount in zip(goal.shares, counted, strict=True)
        ]

    # Reached

    def check_reached(self, today: date) -> list[Goal]:
        """Marks the goals in progress that reached their target, and returns them."""
        reached = []
        for goal in self.list_goals():
            if goal.is_archived or goal.reached_on is not None:
                continue
            saved = self.saved_on(goal, today, today)
            if saved is not None and saved.cents >= goal.target.cents:
                reached.append(dataclasses.replace(goal, reached_on=today, reached_seen=False))
        if reached:
            with self._database.transaction():
                for goal in reached:
                    self._goals.update(goal)
        return reached

    def unseen_reached(self) -> list[Goal]:
        """The goals reached whose notice the user has not seen yet."""
        return [
            goal
            for goal in self.list_goals()
            if goal.reached_on is not None and not goal.reached_seen and not goal.is_archived
        ]

    def mark_seen(self, goal_id: int) -> None:
        goal = self.get(goal_id)
        with self._database.transaction():
            self._goals.update(dataclasses.replace(goal, reached_seen=True))

    # Helpers

    def _counted(self, goal: Goal, balances: dict[int, Money], today: date) -> list[Money | None]:
        """What each share of the goal adds, in the goal's currency. A negative balance
        adds nothing: a goal is not set back by a debt."""
        counted = []
        for share in goal.shares:
            balance = balances[share.account_id]
            amount = Money(max(0, balance.cents) * share.percent // 100, balance.currency)
            counted.append(self._exchange_rates.convert(amount, goal.currency, today))
        return counted

    def _data_since(self, goal: Goal) -> date | None:
        """Since when every account of the goal has data: before that, a month end would
        count an account that did not exist yet."""
        since = self._accounts.data_since()
        days = [since[share.account_id] for share in goal.shares if share.account_id in since]
        return max(days) if days else None

    def _others(self, goal_id: int | None) -> list[Goal]:
        """The goals in progress other than ``goal_id``."""
        return [g for g in self._goals.list() if not g.is_archived and g.id != goal_id]

    def _check_share(self, share: GoalShare, goal_id: int | None) -> None:
        account = self._accounts.get(share.account_id)
        if account.type is AccountType.CREDIT_CARD:
            raise ValidationError("Una tarjeta de crédito no junta dinero para una meta.", "shares")
        if not 1 <= share.percent <= 100:
            raise ValidationError("El porcentaje va de 1 a 100.", field="shares")
        free = self.free_percent(account.id, goal_id)
        if share.percent > free:
            holders = [g for g in self._others(goal_id) if g.share_of(account.id)]
            names = ", ".join(f"«{g.name}»" for g in holders)
            raise ValidationError(
                f"«{account.name}» ya tiene {100 - free} % en {names}: quedan {free} %.",
                field="shares",
            )

    def _checked(self, draft: GoalDraft, goal_id: int | None, today: date) -> Goal:
        name = clean_name(draft.name)
        if draft.target.cents <= 0:
            raise ValidationError("El objetivo tiene que ser mayor que cero.", field="target")
        if draft.target_date is not None and draft.target_date <= today:
            raise ValidationError("Elige una fecha posterior a hoy.", field="target_date")
        if not draft.shares:
            raise ValidationError("Elige al menos una cuenta.", field="shares")
        ids = [share.account_id for share in draft.shares]
        if len(set(ids)) != len(ids):
            raise ValidationError("Cada cuenta va una sola vez.", field="shares")
        for share in draft.shares:
            self._check_share(share, goal_id)
        return Goal(None, name, draft.target, draft.target_date, tuple(draft.shares))
