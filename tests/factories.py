"""Shorthands for building test data."""

from datetime import date

from PySide6.QtWidgets import QApplication

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.services.recurring_charge_service import RecurringChargeDraft
from nodus.services.transaction_service import TransactionDraft
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager

TODAY = date(2026, 11, 5)


def ars(amount: str) -> Money:
    return Money.from_decimal(amount, Currency.ARS)


def usd(amount: str) -> Money:
    return Money.from_decimal(amount, Currency.USD)


def eur(amount: str) -> Money:
    return Money.from_decimal(amount, Currency.EUR)


def clp(amount: str) -> Money:
    return Money.from_decimal(amount, Currency.CLP)


def category_id(services: Services, name: str, kind: TransactionType) -> int:
    """Id of a default category, looked up by name."""
    return next(c.id for c in services.categories.list_categories(kind) if c.name == name)


def expense_draft(
    services: Services, account_id: int, amount: Money, on: date = TODAY, **overrides
) -> TransactionDraft:
    """An expense in "Supermercado y comida", the most common case."""
    values = {
        "account_id": account_id,
        "type": TransactionType.EXPENSE,
        "amount": amount,
        "occurred_on": on,
        "category_id": category_id(services, "Supermercado y comida", TransactionType.EXPENSE),
    }
    return TransactionDraft(**(values | overrides))


def income_draft(
    services: Services, account_id: int, amount: Money, on: date = TODAY, **overrides
) -> TransactionDraft:
    """An income in "Sueldo"."""
    values = {
        "account_id": account_id,
        "type": TransactionType.INCOME,
        "amount": amount,
        "occurred_on": on,
        "category_id": category_id(services, "Sueldo", TransactionType.INCOME),
    }
    return TransactionDraft(**(values | overrides))


def charge_draft(
    services: Services, account_id: int, amount: Money, due: date = TODAY, **overrides
) -> RecurringChargeDraft:
    """A monthly charge in "Servicios", like an internet bill."""
    values = {
        "name": "Internet",
        "amount": amount,
        "account_id": account_id,
        "category_id": category_id(services, "Servicios", TransactionType.EXPENSE),
        "frequency": Frequency.MONTHLY,
        "next_due_on": due,
    }
    return RecurringChargeDraft(**(values | overrides))


def light_theme() -> ThemeManager:
    """A light theme for widgets that need one, built over the running application."""
    return ThemeManager(QApplication.instance(), ThemeMode.LIGHT)


class FakeRegistry:
    """The Run key's ``Nodus`` value, in memory."""

    def __init__(self, value: str | None = None) -> None:
        self.value = value

    def read(self) -> str | None:
        return self.value

    def write(self, command: str) -> None:
        self.value = command

    def delete(self) -> None:
        self.value = None


def data_since(database, day: date) -> None:
    """Dates every account as created on ``day``: the user has had data since then."""
    with database.transaction():
        database.connection.execute("UPDATE accounts SET created_at = ?", (f"{day}T12:00:00",))
