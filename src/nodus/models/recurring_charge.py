"""Fixed expenses that come back every week, month or year, and when they are due next."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from fractions import Fraction

from nodus.models.money import Money
from nodus.models.period import Month


class Frequency(Enum):
    """How often a charge comes back. The value is what the database stores."""

    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"

    @property
    def days(self) -> int:
        """Days between charges, for the frequencies counted in days; 0 otherwise."""
        return {Frequency.WEEKLY: 7, Frequency.BIWEEKLY: 14}.get(self, 0)

    @property
    def months(self) -> int:
        """Months between charges, for the frequencies counted in months; 0 otherwise."""
        return {
            Frequency.MONTHLY: 1,
            Frequency.QUARTERLY: 3,
            Frequency.SEMIANNUAL: 6,
            Frequency.ANNUAL: 12,
        }.get(self, 0)

    @property
    def per_month(self) -> Fraction:
        """How many charges fall in an average month: 52/12 for weekly, 1/12 for annual."""
        if self.days:
            return Fraction(365 // self.days, 12)
        return Fraction(1, self.months)


class DueStatus(Enum):
    """When a charge is due: already late, within ``SOON_DAYS``, or later."""

    OVERDUE = "overdue"
    SOON = "soon"
    LATER = "later"


# A charge due within this many days counts as due soon.
SOON_DAYS = 7


def next_due(day: date, frequency: Frequency, anchor_day: int) -> date:
    """The charge after the one due on ``day``.

    Monthly-based frequencies keep the day of the month the charge was set up with, so a
    charge on the 31st falls on the 28th or 29th in February and on the 31st again in March.
    """
    if frequency.days:
        return day + timedelta(days=frequency.days)
    return Month.of(day).shifted(frequency.months).day(anchor_day)


@dataclass(frozen=True)
class RecurringCharge:
    """An expense that repeats: rent, a service, a subscription.

    Its currency is the account's, or dollars paid from a peso account, as a subscription
    charged to a card. For the latter, ``last_paid_rate`` holds the pesos per dollar of
    its last payment, card taxes included. ``anchor_day`` is the day of the month it was
    set up for, which ``next_due_on`` returns to after short months.
    """

    id: int | None
    name: str
    amount: Money
    account_id: int
    category_id: int
    frequency: Frequency
    anchor_day: int
    next_due_on: date
    is_active: bool = True
    note: str = ""
    last_paid_rate: Decimal | None = None

    def __post_init__(self) -> None:
        if self.amount.cents <= 0:
            raise ValueError("A recurring charge's amount must be positive")
        if not 1 <= self.anchor_day <= 31:
            raise ValueError(f"Invalid anchor day: {self.anchor_day}")

    def monthly_amount(self, payment: Money | None = None) -> Money:
        """What the charge costs in an average month, rounded to the cent: its amount, or
        ``payment`` when what each payment takes is known in another currency."""
        payment = payment or self.amount
        cents = Fraction(payment.cents) * self.frequency.per_month
        return Money(round(cents), payment.currency)

    def following_due(self) -> date:
        """The due date after the current one."""
        return next_due(self.next_due_on, self.frequency, self.anchor_day)

    def days_until(self, today: date) -> int:
        """Days until it is due; negative when it is overdue."""
        return (self.next_due_on - today).days

    def quiet_until(self) -> date:
        """The day «Ya lo vi» lets the warning come back: the day before it is due."""
        return self.next_due_on - timedelta(days=1)

    def can_be_seen(self, today: date) -> bool:
        """Whether «Ya lo vi» makes sense: it warns now, and the day before is still
        ahead, so putting it off leaves at least one quiet day. Due tomorrow, today or
        overdue, it always warns."""
        return (
            self.is_active and self.status(today) is DueStatus.SOON and self.quiet_until() > today
        )

    def seen_key(self, today: date) -> str:
        """How the record of what the user saw names this charge today: its due date and
        how near it is. Seen while due soon, it is new again the day before it is due,
        and again once overdue; the next due date is another charge altogether."""
        if self.days_until(today) < 0:
            stage = "overdue"
        elif self.quiet_until() <= today:
            stage = "near"
        else:
            stage = "soon"
        return f"charge:{self.id}@{self.next_due_on}:{stage}"

    def status(self, today: date) -> DueStatus:
        """Overdue only after its day has passed; the due day itself is still on time."""
        days = self.days_until(today)
        if days < 0:
            return DueStatus.OVERDUE
        return DueStatus.SOON if days <= SOON_DAYS else DueStatus.LATER
