"""Business rules for recurring charges: setting them up, paying them and what is due."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import date

from nodus.database.database import Database
from nodus.database.repositories.recurring_charge_repository import RecurringChargeRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.recurring_charge import Frequency, RecurringCharge
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.errors import ValidationError, clean_name, require_found
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.transaction_service import TransactionDraft, TransactionService

# The dashboard and the notifications look this many days ahead.
UPCOMING_DAYS = 14


@dataclass(frozen=True)
class RecurringChargeDraft:
    """What the user fills in for a recurring charge."""

    name: str
    amount: Money
    account_id: int
    category_id: int
    frequency: Frequency
    next_due_on: date
    note: str = ""


@dataclass(frozen=True)
class RecurringSummary:
    """What the active charges cost together, in pesos.

    Dollar charges are converted at the latest rate; without one they are added up apart
    in ``unconverted_monthly`` instead of being left out silently.
    """

    monthly: Money
    unconverted_monthly: Money
    active: int

    @property
    def yearly(self) -> Money:
        return _times_twelve(self.monthly)

    @property
    def unconverted_yearly(self) -> Money:
        return _times_twelve(self.unconverted_monthly)


def _times_twelve(money: Money) -> Money:
    return Money(money.cents * 12, money.currency)


class RecurringChargeService:
    CURRENCY = Currency.ARS

    def __init__(
        self,
        database: Database,
        charges: RecurringChargeRepository,
        transaction_repository: TransactionRepository,
        transactions: TransactionService,
        exchange_rates: ExchangeRateService,
    ) -> None:
        self._database = database
        self._charges = charges
        self._transaction_repository = transaction_repository
        self._transactions = transactions
        self._exchange_rates = exchange_rates

    def create(self, draft: RecurringChargeDraft) -> RecurringCharge:
        charge = self._build(None, draft, anchor_day=draft.next_due_on.day)
        with self._database.transaction():
            return self._charges.add(charge)

    def update(self, charge_id: int, draft: RecurringChargeDraft) -> None:
        """Keeps the anchor day unless the date or the frequency change, so renaming a
        charge due on the 28th of February doesn't move it off the 31st."""
        current = self.get(charge_id)
        same_schedule = (draft.next_due_on, draft.frequency) == (
            current.next_due_on,
            current.frequency,
        )
        anchor_day = current.anchor_day if same_schedule else draft.next_due_on.day
        charge = self._build(charge_id, draft, anchor_day, current.is_active)
        with self._database.transaction():
            self._charges.update(charge)

    def delete(self, charge_id: int) -> None:
        self.get(charge_id)
        with self._database.transaction():
            self._charges.delete(charge_id)

    def set_active(self, charge_id: int, active: bool) -> None:
        """Pausing keeps the charge but leaves it out of totals, the dashboard and notices."""
        self._save(dataclasses.replace(self.get(charge_id), is_active=active))

    def get(self, charge_id: int) -> RecurringCharge:
        return require_found(self._charges.get(charge_id), "El cargo recurrente no existe.")

    def list_charges(self) -> list[RecurringCharge]:
        """By next due date, then by name."""
        return sorted(self._charges.list(), key=lambda c: (c.next_due_on, c.name.casefold()))

    def count_for_account(self, account_id: int) -> int:
        return self._charges.count_for_account(account_id)

    def pay(self, charge_id: int, amount: Money, day: date, account_id: int) -> Transaction:
        """Records the expense and moves the charge to its next date.

        The next date follows the one that was due, not the payment day, so paying late
        doesn't shift the calendar. Both changes are saved together or not at all.
        """
        charge = self._require_active(charge_id)
        transaction = self._transactions.validated(
            TransactionDraft(
                account_id, TransactionType.EXPENSE, amount, day, charge.category_id, charge.name
            )
        )
        advanced = dataclasses.replace(charge, next_due_on=charge.following_due())
        with self._database.transaction():
            saved = self._transaction_repository.add(transaction)
            self._charges.update(advanced)
        return saved

    def skip(self, charge_id: int) -> None:
        """Moves the charge to its next date without recording anything."""
        charge = self._require_active(charge_id)
        self._save(dataclasses.replace(charge, next_due_on=charge.following_due()))

    def summary(self, today: date) -> RecurringSummary:
        monthly = Money.zero(self.CURRENCY)
        unconverted = Money.zero(Currency.USD)
        active = [c for c in self._charges.list() if c.is_active]
        for charge in active:
            amount = charge.monthly_amount()
            converted = self._exchange_rates.convert(amount, self.CURRENCY, today)
            if converted is None:
                unconverted += amount
            else:
                monthly += converted
        return RecurringSummary(monthly, unconverted, len(active))

    def upcoming(self, today: date, days: int = UPCOMING_DAYS) -> list[RecurringCharge]:
        """Active charges that are overdue or due within ``days``, the oldest first."""
        return [c for c in self.list_charges() if c.is_active and c.days_until(today) <= days]

    def _require_active(self, charge_id: int) -> RecurringCharge:
        charge = self.get(charge_id)
        if not charge.is_active:
            raise ValidationError(f"«{charge.name}» está en pausa; reanúdalo para pagarlo.")
        return charge

    def _save(self, charge: RecurringCharge) -> None:
        with self._database.transaction():
            self._charges.update(charge)

    def _build(
        self,
        charge_id: int | None,
        draft: RecurringChargeDraft,
        anchor_day: int,
        is_active: bool = True,
    ) -> RecurringCharge:
        """Checks the draft with the same rules as an expense: an active account in the
        amount's currency and an expense category."""
        name = clean_name(draft.name)
        self._transactions.validated(
            TransactionDraft(
                draft.account_id,
                TransactionType.EXPENSE,
                draft.amount,
                draft.next_due_on,
                draft.category_id,
            )
        )
        return RecurringCharge(
            id=charge_id,
            name=name,
            amount=draft.amount,
            account_id=draft.account_id,
            category_id=draft.category_id,
            frequency=draft.frequency,
            anchor_day=anchor_day,
            next_due_on=draft.next_due_on,
            is_active=is_active,
            note=draft.note.strip(),
        )
