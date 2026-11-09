"""Recurring charges section: what is due, what it all costs per month, and each charge."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
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
from nodus.services.recurring_charge_service import RecurringSummary
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog, RecurringChargeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import FREQUENCY_LABELS, charge_amount_text
from nodus.ui.pages.dashboard_cards import FigureTile, due_status_label
from nodus.ui.pages.page import Page
from nodus.ui.theme.design import Space
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.color import ColorDot
from nodus.ui.widgets.pay_button import PayButton
from nodus.ui.widgets.row_actions import MoreButton, RowAction, install_row_actions
from nodus.ui.widgets.style import clear_layout, set_style_property

GROUP_TITLES = {
    DueStatus.OVERDUE: "Vencidos",
    DueStatus.SOON: "Próximos 7 días",
    DueStatus.LATER: "Más adelante",
}
PAUSED_TITLE = "En pausa"
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


class RecurringChargeRow(QWidget):
    """One charge: category color, name and schedule, amount, when it is due and its actions.

    Paused charges can't be paid or skipped, only resumed, edited or deleted.
    """

    pay_requested = Signal(object)  # RecurringCharge
    skip_requested = Signal(object)
    edit_requested = Signal(object)
    pause_toggled = Signal(object)
    delete_requested = Signal(object)

    def __init__(
        self,
        charge: RecurringCharge,
        category: Category,
        account_name: str,
        today: date,
        amount_text: str | None = None,
    ) -> None:
        super().__init__()
        self.charge = charge
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        layout.setSpacing(Space.M)
        layout.addWidget(ColorDot(category.color))

        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(charge.name)
        name.setObjectName("RowTitle")
        detail = QLabel(f"{FREQUENCY_LABELS[charge.frequency]} · {account_name} · {category.name}")
        set_style_property(detail, "muted", True)
        texts.addWidget(name)
        texts.addWidget(detail)
        layout.addLayout(texts, stretch=1)

        amounts = QVBoxLayout()
        amounts.setSpacing(0)
        amount = QLabel(amount_text or charge.amount.format())
        amount.setObjectName("RowAmount")
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label = (
            due_status_label(charge, today) if charge.is_active else QLabel(PAUSED_TITLE)
        )
        if not charge.is_active:
            set_style_property(self.status_label, "muted", True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        amounts.addWidget(amount)
        amounts.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(amounts)

        self.pay_button = PayButton()
        self.pay_button.clicked.connect(lambda: self.pay_requested.emit(charge))
        layout.addWidget(self.pay_button)
        if not charge.is_active:  # a paused charge is not paid; its room stays
            self.pay_button.hide()

        self.more_button = MoreButton(self.actions)
        layout.addWidget(self.more_button)
        install_row_actions(self, self.actions)

    def actions(self) -> list[RowAction]:
        """Everything the charge allows, for the «⋯» and the right click."""
        charge = self.charge
        result = []
        if charge.is_active:
            result += [
                RowAction("Pagar", lambda: self.pay_requested.emit(charge), "pay", default=True),
                RowAction("Omitir", lambda: self.skip_requested.emit(charge), "skip"),
            ]
        return result + [
            # A paused charge cannot be paid; editing is what it opens.
            RowAction(
                "Editar",
                lambda: self.edit_requested.emit(charge),
                "pencil",
                default=not charge.is_active,
            ),
            RowAction(
                "Pausar" if charge.is_active else "Reanudar",
                lambda: self.pause_toggled.emit(charge),
                "pause" if charge.is_active else "play",
            ),
            RowAction(
                "Eliminar", lambda: self.delete_requested.emit(charge), "trash", destructive=True
            ),
        ]


class RecurringPage(Page):
    """The totals on top, then the charges grouped by when they are due."""

    def __init__(self, services: Services, event_bus: EventBus) -> None:
        super().__init__("Cargos recurrentes")
        self._services = services
        self._event_bus = event_bus
        self.create_button = self.add_header_button("Agregar cargo", primary=True)
        self.create_button.clicked.connect(lambda: self.open_charge_dialog())

        container = QWidget()
        self._sections = QVBoxLayout(container)
        self._sections.setContentsMargins(0, 0, 0, 0)
        self._sections.setSpacing(Space.L)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)
        self.rows: list[RecurringChargeRow] = []
        self.monthly_label = QLabel()
        self.yearly_label = QLabel()
        self.active_label = QLabel()

        for signal in (
            event_bus.recurring_changed,
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self, today: date | None = None) -> None:
        today = today or date.today()
        clear_layout(self._sections)
        self.rows = []
        charges = self._services.recurring.list_charges()
        if not charges:
            self._sections.addWidget(self._empty_state())
            self._sections.addStretch()
            return
        self._sections.addWidget(self._summary_card(self._services.recurring.summary(today)))
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
        self._sections.addStretch()

    # Actions

    def open_charge_dialog(self, charge: RecurringCharge | None = None) -> None:
        RecurringChargeDialog(self._services, self._event_bus, charge, parent=self.window()).exec()

    def open_pay_dialog(self, charge: RecurringCharge) -> None:
        PayChargeDialog(self._services, self._event_bus, charge, parent=self.window()).exec()

    def skip(self, charge: RecurringCharge) -> None:
        skip_charge(self._services, self._event_bus, charge)

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

    def _summary_card(self, summary: RecurringSummary) -> Card:
        card = Card()
        tiles = QHBoxLayout()
        tiles.setSpacing(Space.S)
        monthly, yearly = summary_text(summary)
        self.monthly_label = QLabel(monthly)
        self.yearly_label = QLabel(yearly)
        self.active_label = QLabel(str(summary.active))
        for caption, value in (
            ("Por mes", self.monthly_label),
            ("Por año", self.yearly_label),
            ("Activos", self.active_label),
        ):
            tiles.addWidget(FigureTile(caption, value), stretch=1)
        card.body.addLayout(tiles)
        return card

    def _empty_state(self) -> Card:
        card = Card()
        title = QLabel("Aún no hay cargos recurrentes")
        title.setObjectName("RowTitle")
        text = QLabel(EMPTY_TEXT)
        text.setWordWrap(True)
        set_style_property(text, "muted", True)
        card.body.addWidget(title)
        card.body.addWidget(text)
        return card


def skip_charge(services: Services, event_bus: EventBus, charge: RecurringCharge) -> None:
    """Moves ``charge`` to its next due date without recording a payment."""
    services.recurring.skip(charge.id)
    event_bus.recurring_changed.emit()
