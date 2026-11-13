"""The application's main sections, and what other pages ask the transactions page to show."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.models.period import Month, Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services


class PageId(Enum):
    """A section reachable from the sidebar. Each value is (label, icon name)."""

    DASHBOARD = ("Dashboard", "dashboard")
    ACCOUNTS = ("Cuentas", "accounts")
    TRANSACTIONS = ("Transacciones", "transactions")
    RECURRING = ("Recurrentes", "repeat")
    BUDGETS = ("Presupuestos", "budget")
    GOALS = ("Metas", "goal")
    ANALYSIS = ("Análisis", "analysis")
    CATEGORIES = ("Categorías", "categories")
    PAYEES = ("Beneficiarios", "payee")
    TAGS = ("Etiquetas", "tags")
    SETTINGS = ("Ajustes", "settings")

    @property
    def label(self) -> str:
        return self.value[0]

    @property
    def icon_name(self) -> str:
        return self.value[1]


class DetailId(Enum):
    """A page about one item (an account, a payee, a tag, a goal), reached from its list and not
    from the sidebar. Each value is the list page it belongs to, which the sidebar keeps
    selected and «‹ Volver» goes back to."""

    ACCOUNT = PageId.ACCOUNTS
    PAYEE = PageId.PAYEES
    TAG = PageId.TAGS
    GOAL = PageId.GOALS

    @property
    def list_page(self) -> PageId:
        return self.value


@dataclass(frozen=True)
class TransactionFocus:
    """The movements a page sends the user to: a period, narrowed to one category, payee,
    tag or account when set. One object instead of a growing list of signal arguments."""

    period: Period
    category_id: int | None = None
    payee_id: int | None = None
    tag_id: int | None = None
    account_id: int | None = None


def history_period(first_on: date, last_on: date) -> Period:
    """The whole months from ``first_on`` to ``last_on`` or today, whichever is later, to
    show everything a payee or tag has, scheduled movements included."""
    return Period.of_months(Month.of(first_on), Month.of(max(last_on, date.today())))


def history_focus(
    services: Services, account_id: int | None = None, category_id: int | None = None
) -> TransactionFocus | None:
    """Every movement of an account or a category, from its first to today; None when it
    has none, so menus can disable «Ver movimientos»."""
    span = services.transactions.date_range(
        TransactionFilter(account_id=account_id, category_id=category_id)
    )
    if span is None:
        return None
    return TransactionFocus(history_period(*span), category_id=category_id, account_id=account_id)
