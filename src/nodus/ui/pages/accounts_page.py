"""Accounts section: net worth summary and the list of accounts."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from nodus.models.account import Account
from nodus.models.money import Money
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import ACCOUNT_TYPE_LABELS
from nodus.ui.navigation import PageId
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.money_label import MoneyLabel, masked
from nodus.ui.widgets.net_worth_card import NetWorthCard, signed
from nodus.ui.widgets.style import clear_layout, set_style_property


class AccountRow(QWidget):
    """One account: currency badge, name and type, balance, and its actions.

    A savings or investment account also shows what it gained by itself and offers to
    update its value.
    """

    edit_requested = Signal(object)  # Account
    value_update_requested = Signal(object)  # Account
    archive_toggled = Signal(object)  # Account
    delete_requested = Signal(object)  # Account

    def __init__(
        self,
        account: Account,
        balance: Money,
        hide_balance: bool = False,
        value_change: Money | None = None,
    ) -> None:
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
        details = [ACCOUNT_TYPE_LABELS[account.type], account.currency.value]
        if value_change is not None and not value_change.is_zero:
            change = masked(value_change) if hide_balance else signed(value_change)
            details.append(f"Rendimiento {change}")
        subtitle = QLabel(" · ".join(details))
        set_style_property(subtitle, "muted", True)
        texts.addWidget(name)
        texts.addWidget(subtitle)
        layout.addLayout(texts, stretch=1)

        balance_label = MoneyLabel()
        balance_label.set_hidden(hide_balance)
        balance_label.set_money(balance)
        balance_label.setObjectName("RowAmount")
        layout.addWidget(balance_label)

        self.value_button = self._small_button("Actualizar valor")
        self.value_button.setToolTip(
            "Anota lo que vale hoy; la diferencia es rendimiento, no un ingreso"
        )
        self.value_button.clicked.connect(lambda: self.value_update_requested.emit(account))
        # Hidden but keeping its room, so every balance lines up.
        policy = self.value_button.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.value_button.setSizePolicy(policy)
        self.value_button.setVisible(account.type.changes_value and not account.is_archived)
        layout.addWidget(self.value_button)
        self.edit_button = self._small_button("Editar")
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(account))
        self.archive_button = self._small_button(
            "Desarchivar" if account.is_archived else "Archivar"
        )
        self.archive_button.clicked.connect(lambda: self.archive_toggled.emit(account))
        self.delete_button = self._small_button("Eliminar")
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(account))
        for button in (self.edit_button, self.archive_button, self.delete_button):
            layout.addWidget(button)

    @staticmethod
    def _small_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("SmallButton")
        return button


class AccountsPage(Page):
    """Net worth in pesos and dollars, then active and archived accounts."""

    navigate_requested = Signal(object)  # PageId

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Cuentas")
        self._services = services
        self._event_bus = event_bus
        self.create_button = self.add_header_button("Crear cuenta", primary=True)
        self.create_button.clicked.connect(lambda: self.open_account_dialog())

        container = QWidget()
        page_layout = QVBoxLayout(container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)
        # The net worth card lives as long as the page, so its figures count to new values.
        self.net_worth_card = NetWorthCard(services, theme_manager, compact=True)
        self.net_worth_card.set_amounts_hidden(services.settings.amounts_hidden())
        event_bus.amounts_hidden_changed.connect(self.net_worth_card.set_amounts_hidden)
        self.net_worth_card.rate_requested.connect(
            lambda: self.navigate_requested.emit(PageId.SETTINGS)
        )
        page_layout.addWidget(self.net_worth_card)
        self._sections = QVBoxLayout()
        self._sections.setSpacing(16)
        page_layout.addLayout(self._sections)
        page_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        for signal in (
            event_bus.accounts_changed,
            event_bus.transactions_changed,
            event_bus.exchange_rates_changed,
            event_bus.amounts_hidden_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        clear_layout(self._sections)
        accounts = self._services.accounts.list_accounts(include_archived=True)
        self.net_worth_card.setVisible(bool(accounts))
        if not accounts:
            self._sections.addWidget(self._empty_state())
            return
        balances = self._services.accounts.balances()
        active = [a for a in accounts if not a.is_archived]
        archived = [a for a in accounts if a.is_archived]
        self.net_worth_card.show_day(date.today())
        self._sections.addWidget(self._accounts_card("Cuentas activas", active, balances))
        if archived:
            self._sections.addWidget(self._accounts_card("Archivadas", archived, balances))

    def open_account_dialog(self, account: Account | None = None) -> None:
        AccountDialog(self._services, self._event_bus, account, parent=self.window()).exec()

    def open_value_dialog(self, account: Account) -> None:
        ValueAdjustmentDialog(self._services, self._event_bus, account, parent=self.window()).exec()

    def _accounts_card(
        self, title: str, accounts: list[Account], balances: dict[int, Money]
    ) -> Card:
        card = Card(title)
        if not accounts:
            empty = QLabel("No hay cuentas activas.")
            set_style_property(empty, "muted", True)
            card.body.addWidget(empty)
        for account in accounts:
            value_change = (
                self._services.accounts.value_change(account.id)
                if account.type.changes_value
                else None
            )
            row = AccountRow(
                account,
                balances[account.id],
                self._services.settings.amounts_hidden(),
                value_change,
            )
            row.edit_requested.connect(self.open_account_dialog)
            row.value_update_requested.connect(self.open_value_dialog)
            row.archive_toggled.connect(self._toggle_archived)
            row.delete_requested.connect(self.delete_account)
            card.body.addWidget(row)
        return card

    def _toggle_archived(self, account: Account) -> None:
        self._services.accounts.set_archived(account.id, not account.is_archived)
        self._event_bus.accounts_changed.emit()

    def delete_account(self, account: Account) -> None:
        if not confirm(self.window(), "Eliminar cuenta", self._delete_warning(account)):
            return
        self._services.accounts.delete(account.id)
        self._event_bus.accounts_changed.emit()
        self._event_bus.transactions_changed.emit()

    def _delete_warning(self, account: Account) -> str:
        movements, transfers = self._services.accounts.transaction_count(account.id)
        sentences = [f"Se va a eliminar la cuenta «{account.name}»."]
        if movements == 0:
            sentences.append("No tiene transacciones.")
        elif movements == 1:
            sentences.append("Su única transacción también se elimina.")
        else:
            sentences.append(f"Sus {movements} transacciones también se eliminan.")
        if transfers == 1:
            sentences.append(
                "Incluye una transferencia, así que cambia el saldo de la otra cuenta."
            )
        elif transfers > 1:
            sentences.append(
                f"Incluye {transfers} transferencias, así que cambia el saldo de las otras cuentas."
            )
        charges = self._services.recurring.count_for_account(account.id)
        if charges == 1:
            sentences.append("También se elimina su cargo recurrente.")
        elif charges > 1:
            sentences.append(f"También se eliminan sus {charges} cargos recurrentes.")
        if movements:
            sentences.append("Para conservar el historial, archívala en su lugar.")
        return " ".join(sentences)

    def _empty_state(self) -> Card:
        card = Card()
        title = QLabel("Todavía no hay cuentas")
        title.setObjectName("RowTitle")
        text = QLabel("Una por cada lugar donde tengas dinero: banco, efectivo, dólares.")
        text.setWordWrap(True)
        set_style_property(text, "muted", True)
        card.body.addWidget(title)
        card.body.addWidget(text)
        return card
