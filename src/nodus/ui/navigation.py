"""The application's main sections, and what other pages ask the transactions page to show."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.models.period import Month, Period


class PageId(Enum):
    """A section reachable from the sidebar. Each value is (label, icon name)."""

    DASHBOARD = ("Dashboard", "dashboard")
    ACCOUNTS = ("Cuentas", "accounts")
    TRANSACTIONS = ("Transacciones", "transactions")
    RECURRING = ("Recurrentes", "repeat")
    BUDGETS = ("Presupuestos", "budget")
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


@dataclass(frozen=True)
class TransactionFocus:
    """The movements a page sends the user to: a period, narrowed to one category, payee
    or tag when set. One object instead of a growing list of signal arguments."""

    period: Period
    category_id: int | None = None
    payee_id: int | None = None
    tag_id: int | None = None


def history_period(first_on: date, last_on: date) -> Period:
    """The whole months from ``first_on`` to ``last_on`` or today, whichever is later, to
    show everything a payee or tag has, scheduled movements included."""
    return Period.of_months(Month.of(first_on), Month.of(max(last_on, date.today())))
