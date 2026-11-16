"""Recurring charges section: what is due, what it all costs per month, and each charge."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus.models.category import Category
from nodus.models.recurring_charge import DueStatus, RecurringCharge
from nodus.services.container import Services
from nodus.services.installment_service import InstallmentSummary
from nodus.services.recurring_charge_service import RecurringSummary
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog, RecurringChargeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import FREQUENCY_LABELS, charge_amount_text, due_label
from nodus.ui.navigation import PageId
from nodus.ui.pages.dashboard_cards import (
    FigureTile,
    due_status_label,
    muted_label,
    reminder_day,
    seen_actions,
    status_pill,
)
from nodus.ui.pages.page import Page
from nodus.ui.pages.transaction_list_view import (
    delete_transactions,
    edit_transaction,
    pay_off_actions,
)
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder, TransactionListItem
from nodus.ui.undo import offer_undo
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.empty_state import empty_page_card
from nodus.ui.widgets.pay_button import PayButton
from nodus.ui.widgets.row_actions import Effect, RowAction
from nodus.ui.widgets.schedule_row import ScheduleRow
from nodus.ui.widgets.style import clear_layout, set_style_property
from nodus.ui.widgets.toast import show_toast, toast_host

GROUP_TITLES = {
    DueStatus.OVERDUE: "Vencidos",
    DueStatus.SOON: "Próximos 7 días",
    DueStatus.LATER: "Más adelante",
}
PAUSED_TITLE = "En pausa"
INSTALLMENTS_TITLE = "Cuotas"
EMPTY_TEXT = (
    "Anota acá lo que pagas todos los meses o todos los años: el alquiler, los servicios, "
    "Netflix, el gimnasio. Nodus te avisa cuándo vence cada uno y cuánto suman por mes."
)


def summary_text(summary: RecurringSummary) -> tuple[str, str]:
    """The monthly and yearly totals, with dollar charges that lack a rate added apart."""
    monthly, yearly = summary.monthly.format(), summary.yearly.format()
    if not summary.unconverted_monthly.is_zero:
        monthly += f" + {summary.unconverted_monthly.format()}"
        yearly += f" + {summary.unconverted_yearly.format()}"
    return monthly, yearly


class RecurringChargeRow(ScheduleRow):
    """One charge: category color, name and schedule, amount, when it is due, the ✓ that
    pays it and its menu.

    Paused charges can't be paid or skipped, only resumed, edited or deleted.
    """

    pay_requested = Signal(object)  # RecurringCharge
    skip_requested = Signal(object)
    edit_requested = Signal(object)
    pause_toggled = Signal(object)
    delete_requested = Signal(object)
    seen_toggled = Signal(object)

    def __init__(
        self,
        charge: RecurringCharge,
        category: Category,
        account_name: str,
        today: date,
        amount_text: str | None = None,
    ) -> None:
        self._today = today
        if charge.is_active:
            status = due_status_label(charge, today)
        else:
            status = QLabel(PAUSED_TITLE)
            set_style_property(status, "muted", True)
        pay_button = PayButton()
        super().__init__(
            category.color,
            charge.name,
            f"{FREQUENCY_LABELS[charge.frequency]} · {account_name} · {category.name}",
            amount_text or charge.amount.format(),
            status,
            self.actions,
            pay_button,
        )
        self.charge = charge
        self.pay_button = pay_button
        self.pay_button.clicked.connect(lambda: self.pay_requested.emit(charge))
        if not charge.is_active:  # a paused charge is not paid; its room stays
            self.pay_button.hide()

    def actions(self) -> list[RowAction]:
        """Everything the charge allows, for the «⋯» and the right click."""
        charge = self.charge
        result = []
        if charge.is_active:
            result += [
                RowAction(
                    "Pagar",
                    lambda: self.pay_requested.emit(charge),
                    "pay",
                    default=True,
                    effect=Effect.OPEN,
                ),
                RowAction(
                    "Omitir",
                    lambda: self.skip_requested.emit(charge),
                    "skip",
                    effect=Effect.UNDOABLE,
                ),
                *seen_actions(charge, self._today, self.seen_toggled),
            ]
        return result + [
            # A paused charge cannot be paid; editing is what it opens.
            RowAction(
                "Editar",
                lambda: self.edit_requested.emit(charge),
                "pencil",
                default=not charge.is_active,
                effect=Effect.OPEN,
            ),
            RowAction(
                "Pausar" if charge.is_active else "Reanudar",
                lambda: self.pause_toggled.emit(charge),
                "pause" if charge.is_active else "play",
                effect=Effect.TOGGLE,
            ),
            RowAction(
                "Eliminar",
                lambda: self.delete_requested.emit(charge),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]


class InstallmentPlanRow(ScheduleRow):
    """A purchase in installments: what was bought, how far it goes («3 de 6 · Visa ·
    Hogar»), the next installment and when it comes off.

    It has no ✓: each installment comes off the account by itself on its day. Its menu is
    the one an installment has in Transacciones.
    """

    def __init__(
        self,
        summary: InstallmentSummary,
        item: TransactionListItem,
        color: str,
        today: date,
        actions: list[RowAction],
    ) -> None:
        upcoming = summary.upcoming
        assert upcoming is not None
        plan = summary.plan
        super().__init__(
            color,
            summary.first.note or item.category_name,
            f"{summary.paid} de {plan.count} · {item.account_text} · {item.category_name}",
            upcoming.amount.format(),
            status_pill(due_label((upcoming.occurred_on - today).days), "neutral"),
            lambda: actions,
        )
        self.summary = summary


class RecurringPage(Page):
    """The totals on top, then the charges grouped by when they are due, and the purchases
    in installments still running."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.RECURRING.label)
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self.create_button = self.add_header_button("Agregar cargo", primary=True)
        self.create_button.clicked.connect(lambda: self.open_charge_dialog())

        # What the short name covers, said once under the title.
        self.content_layout.addWidget(
            muted_label("Pagos que se repiten: servicios, suscripciones, alquiler.")
        )
        container = QWidget()
        self._sections = QVBoxLayout(container)
        self._sections.setContentsMargins(0, 0, 0, 0)
        self._sections.setSpacing(Space.L)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)
        self.rows: list[RecurringChargeRow] = []
        self.installment_rows: list[InstallmentPlanRow] = []
        self.monthly_label = QLabel()
        self.installments_label = QLabel()
        self.yearly_label = QLabel()
        self.active_label = QLabel()

        for signal in (
            event_bus.recurring_changed,
            event_bus.transactions_changed,
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self, today: date | None = None) -> None:
        today = today or date.today()
        clear_layout(self._sections)
        self.rows = []
        self.installment_rows = []
        charges = self._services.recurring.list_charges()
        purchases = self._services.installments.summaries(today)
        if not charges and not purchases:
            self._sections.addWidget(self._empty_state())
            self._sections.addStretch()
            return
        self._sections.addWidget(self._summary_card(self._services.recurring.summary(today), today))
        categories = {c.id: c for c in self._services.categories.list_categories()}
        accounts = {
            a.id: a.name for a in self._services.accounts.list_accounts(include_archived=True)
        }
        groups: dict[str, list[RecurringCharge]] = {
            title: [] for title in [*GROUP_TITLES.values(), PAUSED_TITLE]
        }
        for charge in charges:
            title = GROUP_TITLES[charge.status(today)] if charge.is_active else PAUSED_TITLE
            groups[title].append(charge)
        for title, members in groups.items():
            if not members:
                continue
            card = Card(f"{title} ({len(members)})")
            for charge in members:
                row = RecurringChargeRow(
                    charge, categories[charge.category_id], accounts[charge.account_id], today,
                    charge_amount_text(
                        charge.amount, self._services.recurring.estimated_payment(charge, today)
                    ),
                )  # fmt: skip
                self._connect(row)
                card.body.addWidget(row)
                self.rows.append(row)
            self._sections.addWidget(card)
        if purchases:
            self._sections.addWidget(self._installments_card(purchases, categories, today))
        self._sections.addStretch()

    def _installments_card(
        self, purchases: list[InstallmentSummary], categories: dict, today: date
    ) -> Card:
        """The purchases with installments to come, soonest first, as Transacciones shows
        their installments."""
        card = Card(f"{INSTALLMENTS_TITLE} ({len(purchases)})")
        items = TransactionListBuilder(self._services).build([p.upcoming for p in purchases])
        for summary, item in zip(purchases, items, strict=True):
            row = InstallmentPlanRow(
                summary,
                item,
                categories[summary.first.category_id].color,
                today,
                self._installment_actions(item),
            )
            card.body.addWidget(row)
            self.installment_rows.append(row)
        return card

    def _installment_actions(self, item: TransactionListItem) -> list[RowAction]:
        """The menu an installment has in Transacciones: its purchase, edited, paid off
        early or deleted."""
        services, event_bus = self._services, self._event_bus
        return [
            RowAction(
                "Editar compra",
                lambda: edit_transaction(
                    services, event_bus, self._theme_manager, item, self.window()
                ),
                "pencil",
                default=True,
                effect=Effect.OPEN,
            ),
            *pay_off_actions(self, services, event_bus, item),
            RowAction(
                "Eliminar compra",
                lambda: delete_transactions(services, event_bus, [item], self.window()),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]

    # Actions

    def open_charge_dialog(self, charge: RecurringCharge | None = None) -> None:
        RecurringChargeDialog(self._services, self._event_bus, charge, parent=self.window()).exec()

    def open_pay_dialog(self, charge: RecurringCharge) -> None:
        PayChargeDialog(self._services, self._event_bus, charge, parent=self.window()).exec()

    def skip(self, charge: RecurringCharge) -> None:
        skip_charge(self, self._services, self._event_bus, charge)

    def toggle_pause(self, charge: RecurringCharge) -> None:
        self._services.recurring.set_active(charge.id, not charge.is_active)
        self._event_bus.recurring_changed.emit()

    def delete_charge(self, charge: RecurringCharge) -> None:
        text = (
            f"Se va a eliminar «{charge.name}». Los pagos ya registrados se conservan "
            "como transacciones."
        )
        if not confirm(self.window(), "Eliminar cargo", text):
            return
        self._services.recurring.delete(charge.id)
        self._event_bus.recurring_changed.emit()

    # Building

    def _connect(self, row: RecurringChargeRow) -> None:
        row.pay_requested.connect(self.open_pay_dialog)
        row.skip_requested.connect(self.skip)
        row.edit_requested.connect(self.open_charge_dialog)
        row.pause_toggled.connect(self.toggle_pause)
        row.delete_requested.connect(self.delete_charge)
        row.seen_toggled.connect(lambda c: toggle_seen(self, self._services, self._event_bus, c))

    def _summary_card(self, summary: RecurringSummary, today: date) -> Card:
        card = Card()
        tiles = QHBoxLayout()
        tiles.setSpacing(Space.S)
        monthly, yearly = summary_text(summary)
        self.monthly_label = QLabel(monthly)
        self.yearly_label = QLabel(yearly)
        self.active_label = QLabel(str(summary.active))
        installments = self._services.installments.monthly(today)
        self.installments_label = QLabel(
            " + ".join(amount.format() for amount in installments) or "—"
        )
        for caption, value in (
            ("Por mes", self.monthly_label),
            ("Por año", self.yearly_label),
            ("Activos", self.active_label),
            ("Cuotas por mes", self.installments_label),
        ):
            tiles.addWidget(FigureTile(caption, value), stretch=1)
        card.body.addLayout(tiles)
        return card

    def _empty_state(self) -> Card:
        card, _state = empty_page_card("Todavía no hay cargos recurrentes", EMPTY_TEXT)
        return card


def toggle_seen(
    widget: QWidget, services: Services, event_bus: EventBus, charge: RecurringCharge
) -> None:
    """«Ya lo vi» on ``charge``, or «Volver a avisarme» when it is put off, told in a
    toast with the day its warning comes back."""
    today = date.today()
    if charge.is_quiet(today):
        services.recurring.remind_again(charge.id)
        text = f"Te volvemos a avisar de {charge.name}."
    else:
        day = services.recurring.mark_seen(charge.id, today)
        text = f"Te recordamos {charge.name} {reminder_day(day, today)}."
    host = toast_host(widget)  # the row that asked is rebuilt by the refresh
    event_bus.recurring_changed.emit()
    if host is not None:
        show_toast(host, text)


def skip_charge(
    widget: QWidget, services: Services, event_bus: EventBus, charge: RecurringCharge
) -> None:
    """Moves ``charge`` to its next due date without recording a payment, with
    «Deshacer» in a toast."""
    services.recurring.skip(charge.id)
    event_bus.recurring_changed.emit()
    offer_undo(widget, services, event_bus.recurring_changed)
