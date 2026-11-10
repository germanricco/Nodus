"""Purchases paid in monthly installments ("cuotas"): their calendar and how they split."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from nodus.models.money import Money
from nodus.models.period import Month

MIN_INSTALLMENTS = 2
MAX_INSTALLMENTS = 72


@dataclass(frozen=True)
class Installment:
    """Which installment of which purchase a transaction is: the 3rd of 6."""

    plan_id: int
    number: int
    count: int

    def __post_init__(self) -> None:
        if not 1 <= self.number <= self.count:
            raise ValueError(f"Installment {self.number} of {self.count} does not exist")

    @property
    def label(self) -> str:
        """ "3/6"."""
        return f"{self.number}/{self.count}"


@dataclass(frozen=True)
class InstallmentPlan:
    """The calendar of a purchase in ``count`` monthly installments that add up to ``total``.

    The plan holds only what defines the calendar; what was bought, where and in which
    category lives on its installments, which are ordinary expenses. Every installment falls
    on the day of the month of the first one (the 31st is the last day of shorter months).
    ``settled_on`` is the day the rest was paid off early: the installments due after it
    fall on that day, and clearing it brings the calendar back as it was.
    """

    id: int | None
    count: int
    total: Money
    first_due_on: date
    settled_on: date | None = None

    def __post_init__(self) -> None:
        if not MIN_INSTALLMENTS <= self.count <= MAX_INSTALLMENTS:
            raise ValueError(
                f"A purchase has {MIN_INSTALLMENTS} to {MAX_INSTALLMENTS} installments"
            )
        if self.total.cents < self.count:
            raise ValueError("Each installment must be at least one cent")
        if self.settled_on is not None and self.settled_on < self.first_due_on:
            raise ValueError("A purchase cannot be paid off before its first installment")

    @classmethod
    def from_installment_amount(
        cls, amount: Money, count: int, first_due_on: date, plan_id: int | None = None
    ) -> InstallmentPlan:
        """The plan of ``count`` installments of ``amount`` each, as a card statement shows
        a purchase with interest."""
        return cls(plan_id, count, Money(amount.cents * count, amount.currency), first_due_on)

    def amounts(self) -> list[Money]:
        """What each installment is worth. The cents that do not divide evenly go to the
        first one, so the installments add up to the total exactly."""
        share, rest = divmod(self.total.cents, self.count)
        currency = self.total.currency
        return [Money(share + rest, currency)] + [Money(share, currency)] * (self.count - 1)

    def due_dates(self) -> list[date]:
        """The day each installment comes off the account, in order."""
        first = Month.of(self.first_due_on)
        anchor = self.first_due_on.day
        days = [first.shifted(i).day(anchor) for i in range(self.count)]
        if self.settled_on is None:
            return days
        return [min(day, self.settled_on) for day in days]

    def schedule(self) -> list[tuple[int, date, Money]]:
        """Number, day and amount of every installment."""
        return [
            (number, day, amount)
            for number, (day, amount) in enumerate(
                zip(self.due_dates(), self.amounts(), strict=True), 1
            )
        ]

    def due_count(self, today: date) -> int:
        """How many installments have already come off the account; today's counts."""
        return sum(1 for day in self.due_dates() if day <= today)

    def remaining(self, today: date) -> Money:
        """What is still to come off the account after ``today``."""
        return sum(
            (amount for _number, day, amount in self.schedule() if day > today),
            Money.zero(self.total.currency),
        )
