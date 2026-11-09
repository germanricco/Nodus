"""Accounts section: net worth summary and the list of accounts."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from nodus.models.account import Account
from nodus.models.money import Money
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import ACCOUNT_TYPE_LABELS
from nodus.ui.navigation import PageId, history_focus
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.money_label import MoneyLabel, masked
from nodus.ui.widgets.net_worth_card import NetWorthCard, signed
from nodus.ui.widgets.reorderable_list import ReorderableList
from nodus.ui.widgets.row_actions import MoreButton, RowAction, install_context_menu
from nodus.ui.widgets.style import clear_layout, set_style_property


class AccountRow(QWidget):
    """One account: currency badge, name and type, balance, and the menu of its actions.

    A savings or investment account also shows what it gained by itself, and its menu
    offers to update its value.
    """

    edit_requested = Signal(object)  # Account
    transactions_requested = Signal(object)  # Account
    value_update_requested = Signal(object)  # Account
    archive_toggled = Signal(object)  # Account
    delete_requested = Signal(object)  # Account

    def __init__(
        self,
        account: Account,
        balance: Money,
        hide_balance: bool = False,
        value_change: Money | None = None,
        has_movements: bool = True,
    ) -> None:
        super().__init__()
        self.account = account
        self.has_movements = has_movements
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

        self.more_button = MoreButton(self.actions)
        layout.addWidget(self.more_button)
        install_context_menu(self, self.actions)

    @property
    def can_update_value(self) -> bool:
        """Savings and investments change value by themselves, until they are archived."""
        return self.account.type.changes_value and not self.account.is_archived

    def actions(self) -> list[RowAction]:
        """Everything the account allows, for the «⋯» and the right click."""
        account = self.account
        result = [
            RowAction(
                "Ver movimientos",
                lambda: self.transactions_requested.emit(account),
                "list",
                enabled=self.has_movements,
            )
        ]
        if self.can_update_value:
            result.append(
                RowAction(
                    "Actualizar valor", lambda: self.value_update_requested.emit(account), "trend"
                )
            )
        return result + [
            RowAction("Editar", lambda: self.edit_requested.emit(account), "pencil"),
            RowAction(
                "Desarchivar" if account.is_archived else "Archivar",
                lambda: self.archive_toggled.emit(account),
                "archive",
            ),
            RowAction(
                "Eliminar", lambda: self.delete_requested.emit(account), "trash", destructive=True
            ),
        ]


class AccountsPage(Page):
    """Net worth in pesos and dollars, then active and archived accounts.

    Active accounts are reordered by dragging their handle; the order is saved and shows
    in the sidebar and in every account list.
    """

    navigate_requested = Signal(object)  # PageId
    transactions_requested = Signal(object)  # TransactionFocus

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Cuentas")
        self._services = services
        self._event_bus = event_bus
        self.create_button = self.add_header_button("Agregar cuenta", primary=True)
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
        # The active accounts, when there are enough to reorder.
        self.account_list: ReorderableList | None = None
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
        self.account_list = None
        accounts = self._services.accounts.list_accounts(include_archived=True)
        self.net_worth_card.setVisible(bool(accounts))
        if not accounts:
            self._sections.addWidget(self._empty_state())
            return
        balances = self._services.accounts.balances()
        active = [a for a in accounts if not a.is_archived]
        archived = [a for a in accounts if a.is_archived]
        self.net_worth_card.show_day(date.today())
        self._sections.addWidget(
            self._accounts_card("Cuentas activas", active, balances, reorderable=True)
        )
        if archived:
            self._sections.addWidget(self._accounts_card("Archivadas", archived, balances))

    def open_account_dialog(self, account: Account | None = None) -> None:
        AccountDialog(self._services, self._event_bus, account, parent=self.window()).exec()

    def open_value_dialog(self, account: Account) -> None:
        ValueAdjustmentDialog(self._services, self._event_bus, account, parent=self.window()).exec()

    def _accounts_card(
        self,
        title: str,
        accounts: list[Account],
        balances: dict[int, Money],
        reorderable: bool = False,
    ) -> Card:
        """A card with a row per account; ``reorderable`` gives each a drag handle once
        there is more than one."""
        card = Card(title)
        if not accounts:
            empty = QLabel("No hay cuentas activas.")
            set_style_property(empty, "muted", True)
            card.body.addWidget(empty)
        rows = None
        if reorderable and len(accounts) > 1:
            rows = self.account_list = ReorderableList()
            rows.order_changed.connect(self._save_order)
            card.body.addWidget(rows)
        for account in accounts:
            value_change = (
                self._services.accounts.value_change(account.id)
                if account.type.changes_value
                else None
            )
            focus = history_focus(self._services, account_id=account.id)
            row = AccountRow(
                account,
                balances[account.id],
                self._services.settings.amounts_hidden(),
                value_change,
                has_movements=focus is not None,
            )
            row.transactions_requested.connect(
                lambda _account, focus=focus: self.transactions_requested.emit(focus)
            )
            row.edit_requested.connect(self.open_account_dialog)
            row.value_update_requested.connect(self.open_value_dialog)
            row.archive_toggled.connect(self._toggle_archived)
            row.delete_requested.connect(self.delete_account)
            if rows is None:
                card.body.addWidget(row)
            else:
                rows.add_row(account.id, row)
        return card

    def _save_order(self, account_ids: list[int]) -> None:
        self._services.accounts.reorder(account_ids)
        self._event_bus.accounts_changed.emit()

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
