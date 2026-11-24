"""Shorthands for building test data."""

from datetime import date

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel

from nodus.config.paths import AppPaths
from nodus.database.database import Database
from nodus.i18n import _
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.services.transactions.recurring_charge_service import RecurringChargeDraft
from nodus.services.transactions.transaction_service import TransactionDraft
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.refresh import screen_signals
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
    """Id of a default category, looked up by its Spanish name, also in a database that
    was created in English and so named it in English."""
    return next(
        c.id for c in services.categories.list_categories(kind) if c.name in (name, _(name))
    )


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


def transaction_dialog(
    qtbot,
    services: Services,
    event_bus: EventBus,
    transaction: Transaction | None = None,
    theme: ThemeManager | None = None,
    show: bool = False,
) -> TransactionDialog:
    """The transaction form, new or for ``transaction``, in ``theme`` (the light one by
    default), closed with the test."""
    dialog = TransactionDialog(services, event_bus, theme or light_theme(), transaction)
    qtbot.addWidget(dialog)
    if show:
        dialog.show()
    return dialog


def visible_rows(dialog) -> list[str]:
    """The rows a form shows, top to bottom, by their label: "" for a line under a
    field, and a row across the form (a caption like «OPCIONAL») by its text."""
    form = dialog.form
    rows = []
    for row in range(form.rowCount()):
        spanning = form.itemAt(row, QFormLayout.ItemRole.SpanningRole)
        field = (spanning or form.itemAt(row, QFormLayout.ItemRole.FieldRole)).widget()
        if not form.isRowVisible(field):
            continue
        if spanning is not None:
            captions = [label.text() for label in field.findChildren(QLabel)]
            rows.append(captions[0] if captions else "")
        else:
            label = form.labelForField(field)
            rows.append(label.text() if label else "")
    return rows


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


def table_rows(database, *tables: str) -> dict[str, list[tuple]]:
    """Every row of ``tables`` but the edit times, to tell an undone change from the
    data as it was: undoing gives back the data, not when it was last touched. Sorted, as
    a link put back is the same link even in another place of the table."""
    rows = {}
    for table in tables:
        cursor = database.connection.execute(f"SELECT * FROM {table}")
        kept = [i for i, column in enumerate(cursor.description) if column[0] != "updated_at"]
        rows[table] = sorted((tuple(row[i] for i in kept) for row in cursor.fetchall()), key=repr)
    return rows


def services_for(database: Database) -> Services:
    """The services on ``database``, with their copies in a folder next to it, as in the app."""
    return Services.create(database, AppPaths(database.path.parent).backups_dir)


def in_view(page, event_bus: EventBus, theme_manager: ThemeManager | None = None):
    """``page`` refreshed after every change, as ``MainWindow`` refreshes the page in
    view (``nodus.ui.refresh``): for a page tested on its own."""
    for signal in screen_signals(event_bus):
        signal.connect(lambda *_args: page.request_refresh())
    if theme_manager is not None:
        theme_manager.theme_changed.connect(lambda _theme: page.request_refresh())
    return page
