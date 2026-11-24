"""The application's main sections, and where a click leads: a record to its page
(``RecordLink``), a month or a total to the transactions page (``TransactionFocus``).

One rule, as in Windows: where a click chooses rows (the lists of Categorías,
Beneficiarios and Etiquetas, which merge or delete several at once), a double click opens
the record; everywhere else a single click does, and the row shows it with the light, the
hand and a «›» at its end (``open_cue``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.i18n import N_, _
from nodus.models.period import Month, Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services


class PageId(Enum):
    """A section reachable from the sidebar. Each value is (label, icon name); the label
    is translated where it is shown, through ``label``."""

    DASHBOARD = (N_("Inicio"), "dashboard")
    ACCOUNTS = (N_("Cuentas"), "accounts")
    TRANSACTIONS = (N_("Transacciones"), "transactions")
    RECURRING = (N_("Recurrentes"), "repeat")
    BUDGETS = (N_("Presupuestos"), "budget")
    GOALS = (N_("Metas"), "goal")
    ANALYSIS = (N_("Análisis"), "analysis")
    CATEGORIES = (N_("Categorías"), "categories")
    PAYEES = (N_("Beneficiarios"), "payee")
    TAGS = (N_("Etiquetas"), "tags")
    SETTINGS = (N_("Ajustes"), "settings")

    @property
    def label(self) -> str:
        return _(self.value[0])

    @property
    def icon_name(self) -> str:
        return self.value[1]


class DetailId(Enum):
    """A page about one item (an account, a category, a payee, a tag, a goal), reached from
    its list and not from the sidebar. Each value is the list page it belongs to, which the
    sidebar keeps selected and «‹ Volver» goes back to."""

    ACCOUNT = PageId.ACCOUNTS
    CATEGORY = PageId.CATEGORIES
    PAYEE = PageId.PAYEES
    TAG = PageId.TAGS
    GOAL = PageId.GOALS

    @property
    def list_page(self) -> PageId:
        return self.value

    @property
    def open_text(self) -> str:
        """What a row that leads to this page says under the mouse."""
        return _(OPEN_TEXTS[self])


OPEN_TEXTS = {
    DetailId.ACCOUNT: N_("Abrir la cuenta"),
    DetailId.CATEGORY: N_("Abrir la categoría"),
    DetailId.PAYEE: N_("Abrir el beneficiario"),
    DetailId.TAG: N_("Abrir la etiqueta"),
    DetailId.GOAL: N_("Abrir la meta"),
}


@dataclass(frozen=True)
class TransactionFocus:
    """The movements a page sends the user to: a period, narrowed to one category, payee,
    tag or account when set. One object instead of a growing list of signal arguments."""

    period: Period
    category_id: int | None = None
    payee_id: int | None = None
    tag_id: int | None = None
    account_id: int | None = None


@dataclass(frozen=True)
class RecordLink:
    """A click on something with a page of its own (an account, category, payee, tag or
    goal), wherever it is shown: it leads to that page, where its movements are. Pages
    ask for it with a ``record_requested`` signal; ``MainWindow`` opens it."""

    detail: DetailId
    item_id: int

    @classmethod
    def account(cls, account_id: int) -> RecordLink:
        return cls(DetailId.ACCOUNT, account_id)

    @classmethod
    def category(cls, category_id: int) -> RecordLink:
        return cls(DetailId.CATEGORY, category_id)

    @classmethod
    def payee(cls, payee_id: int) -> RecordLink:
        return cls(DetailId.PAYEE, payee_id)

    @classmethod
    def tag(cls, tag_id: int) -> RecordLink:
        return cls(DetailId.TAG, tag_id)

    @classmethod
    def goal(cls, goal_id: int) -> RecordLink:
        return cls(DetailId.GOAL, goal_id)


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
