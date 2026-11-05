"""Accounts section: net worth summary and the list of accounts."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from nodus.models.account import Account
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.labels import ACCOUNT_TYPE_LABELS
from nodus.ui.pages.page import Page
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.money_label import MoneyLabel
from nodus.ui.widgets.stat import Stat
from nodus.ui.widgets.style import clear_layout, set_style_property


class AccountRow(QWidget):
    """One account: currency badge, name and type, balance, and its actions."""

    edit_requested = Signal(object)  # Account
    archive_toggled = Signal(object)  # Account

    def __init__(self, account: Account, balance: Money) -> None:
        super().__init__()
        self.account = account
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        badge = QLabel(account.currency.value)
        badge.setObjectName("Badge")
        layout.addWidget(badge)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(account.name)
        name.setObjectName("RowTitle")
        subtitle = QLabel(f"{ACCOUNT_TYPE_LABELS[account.type]} · {account.currency.value}")
        set_style_property(subtitle, "muted", True)
        texts.addWidget(name)
        texts.addWidget(subtitle)
        layout.addLayout(texts, stretch=1)

        balance_label = MoneyLabel(balance)
        balance_label.setObjectName("RowAmount")
        layout.addWidget(balance_label)

        self.edit_button = self._small_button("Editar")
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(account))
        self.archive_button = self._small_button(
            "Desarchivar" if account.is_archived else "Archivar"
        )
        self.archive_button.clicked.connect(lambda: self.archive_toggled.emit(account))
        layout.addWidget(self.edit_button)
        layout.addWidget(self.archive_button)

    @staticmethod
    def _small_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("SmallButton")
        return button


class AccountsPage(Page):
    """Net worth in pesos and dollars, then active and archived accounts."""

    def __init__(self, services: Services, event_bus: EventBus) -> None:
        super().__init__("Cuentas")
        self._services = services
        self._event_bus = event_bus
        self.create_button = self.add_header_button("Crear cuenta", primary=True)
        self.create_button.clicked.connect(lambda: self.open_account_dialog())

        container = QWidget()
        self._sections = QVBoxLayout(container)
        self._sections.setContentsMargins(0, 0, 0, 0)
        self._sections.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        for signal in (
            event_bus.accounts_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        clear_layout(self._sections)
        accounts = self._services.accounts.list_accounts(include_archived=True)
        if not accounts:
            self._sections.addWidget(self._empty_state())
            self._sections.addStretch()
            return
        balances = self._services.accounts.balances()
        active = [a for a in accounts if not a.is_archived]
        archived = [a for a in accounts if a.is_archived]
        self._sections.addWidget(self._summary_card())
        self._sections.addWidget(self._accounts_card("Cuentas activas", active, balances))
        if archived:
            self._sections.addWidget(self._accounts_card("Archivadas", archived, balances))
        self._sections.addStretch()

    def open_account_dialog(self, account: Account | None = None) -> None:
        AccountDialog(self._services, self._event_bus, account, parent=self.window()).exec()

    def _summary_card(self) -> Card:
        today = date.today()
        net_worth = self._services.net_worth.net_worth(today)
        card = Card()
        stats = QHBoxLayout()
        stats.setSpacing(40)
        stats.addWidget(Stat("Patrimonio en pesos", net_worth.total_in[Currency.ARS], large=True))
        stats.addWidget(Stat("Patrimonio en dólares", net_worth.total_in[Currency.USD], large=True))
        stats.addStretch()
        stats.addWidget(Stat("En cuentas en pesos", net_worth.by_currency[Currency.ARS]))
        stats.addWidget(Stat("En cuentas en dólares", net_worth.by_currency[Currency.USD]))
        card.body.addLayout(stats)
        note = QLabel(self._rate_note(today))
        set_style_property(note, "muted", True)
        card.body.addWidget(note)
        return card

    def _rate_note(self, today: date) -> str:
        rate = self._services.exchange_rates.rate_on(today)
        if rate is None:
            return "Carga una cotización del dólar en Ajustes para ver el patrimonio convertido."
        value = Money.from_decimal(rate.rate, Currency.ARS).format()
        return f"Cotización usada: US$ 1 = {value} (del {format_date(rate.rate_date)})"

    def _accounts_card(
        self, title: str, accounts: list[Account], balances: dict[int, Money]
    ) -> Card:
        card = Card(title)
        if not accounts:
            empty = QLabel("No hay cuentas activas.")
            set_style_property(empty, "muted", True)
            card.body.addWidget(empty)
        for account in accounts:
            row = AccountRow(account, balances[account.id])
            row.edit_requested.connect(self.open_account_dialog)
            row.archive_toggled.connect(self._toggle_archived)
            card.body.addWidget(row)
        return card

    def _toggle_archived(self, account: Account) -> None:
        self._services.accounts.set_archived(account.id, not account.is_archived)
        self._event_bus.accounts_changed.emit()

    def _empty_state(self) -> Card:
        card = Card()
        title = QLabel("Todavía no hay cuentas")
        title.setObjectName("RowTitle")
        text = QLabel(
            "Crea una cuenta por cada lugar donde tengas dinero: el banco, el efectivo,"
            " los ahorros en dólares. Después vas a poder registrar sus movimientos."
        )
        text.setWordWrap(True)
        set_style_property(text, "muted", True)
        card.body.addWidget(title)
        card.body.addWidget(text)
        return card
