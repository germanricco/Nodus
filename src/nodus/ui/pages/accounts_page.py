"""Accounts section: net worth summary and the list of accounts."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus.models.account import Account
from nodus.models.account_group import AccountGroup
from nodus.models.money import Money
from nodus.services.account_group_service import AccountSection
from nodus.services.container import Services
from nodus.ui.dialogs.account_dialog import AccountDialog
from nodus.ui.dialogs.account_group_dialogs import GroupDialog, MoveToGroupDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import ACCOUNT_TYPE_LABELS
from nodus.ui.navigation import PageId, history_focus
from nodus.ui.pages.page import Page
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.empty_state import EmptyState, empty_page_card
from nodus.ui.widgets.money_label import MoneyLabel, masked, total_text
from nodus.ui.widgets.net_worth_card import NetWorthCard, signed
from nodus.ui.widgets.reorderable_list import ReorderableList, handle_indent
from nodus.ui.widgets.row_actions import MoreButton, RowAction, install_row_actions
from nodus.ui.widgets.style import clear_layout, set_style_property


def account_delete_warning(services: Services, account: Account) -> str:
    """What deleting ``account`` takes with it: its movements, transfers and charges."""
    movements, transfers = services.accounts.transaction_count(account.id)
    sentences = [f"Se va a eliminar la cuenta «{account.name}»."]
    if movements == 0:
        sentences.append("No tiene transacciones.")
    elif movements == 1:
        sentences.append("Su única transacción también se elimina.")
    else:
        sentences.append(f"Sus {movements} transacciones también se eliminan.")
    if transfers == 1:
        sentences.append("Incluye una transferencia, así que cambia el saldo de la otra cuenta.")
    elif transfers > 1:
        sentences.append(
            f"Incluye {transfers} transferencias, así que cambia el saldo de las otras cuentas."
        )
    charges = services.recurring.count_for_account(account.id)
    if charges == 1:
        sentences.append("También se elimina su cargo recurrente.")
    elif charges > 1:
        sentences.append(f"También se eliminan sus {charges} cargos recurrentes.")
    if movements:
        sentences.append("Para conservar el historial, archívala en su lugar.")
    return " ".join(sentences)


def delete_account(
    parent: QWidget, services: Services, event_bus: EventBus, account: Account
) -> bool:
    """Deletes ``account`` once the user confirms, saying what goes with it."""
    if not confirm(parent, "Eliminar cuenta", account_delete_warning(services, account)):
        return False
    services.accounts.delete(account.id)
    event_bus.accounts_changed.emit()
    event_bus.transactions_changed.emit()
    return True


class AccountRow(QWidget):
    """One account: currency badge, name and type, balance, and the menu of its actions.

    A savings or investment account also shows what it gained by itself, and its menu
    offers to update its value.
    """

    detail_requested = Signal(object)  # Account
    edit_requested = Signal(object)  # Account
    transactions_requested = Signal(object)  # Account
    value_update_requested = Signal(object)  # Account
    move_requested = Signal(object)  # Account
    goal_requested = Signal(object)  # Account
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
        layout.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        layout.setSpacing(Space.M)

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
        chevron = QLabel("›")
        set_style_property(chevron, "muted", True)
        layout.addWidget(chevron)
        install_row_actions(self, self.actions)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Abrir la cuenta")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.detail_requested.emit(self.account)

    @property
    def can_update_value(self) -> bool:
        """Savings and investments change value by themselves, until they are archived."""
        return self.account.type.changes_value and not self.account.is_archived

    def actions(self) -> list[RowAction]:
        """Everything the account allows, for the «⋯» and the right click."""
        account = self.account
        result = [
            RowAction("Abrir", lambda: self.detail_requested.emit(account), default=True),
            RowAction(
                "Ver movimientos",
                lambda: self.transactions_requested.emit(account),
                "list",
                enabled=self.has_movements,
            ),
        ]
        if self.can_update_value:
            result.append(
                RowAction(
                    "Actualizar valor", lambda: self.value_update_requested.emit(account), "trend"
                )
            )
        if self.can_update_value:  # what a savings goal is filled with
            result.append(
                RowAction("Usar en una meta…", lambda: self.goal_requested.emit(account), "goal")
            )
        result.append(RowAction("Editar", lambda: self.edit_requested.emit(account), "pencil"))
        if not account.is_archived:  # archived accounts show apart from every group
            result.append(
                RowAction("Mover a grupo…", lambda: self.move_requested.emit(account), "folder")
            )
        return result + [
            RowAction(
                "Desarchivar" if account.is_archived else "Archivar",
                lambda: self.archive_toggled.emit(account),
                "archive",
            ),
            RowAction(
                "Eliminar", lambda: self.delete_requested.emit(account), "trash", destructive=True
            ),
        ]


def group_delete_warning(group: AccountGroup, count: int) -> str:
    """What deleting ``group`` does: its accounts stay, in no group."""
    sentence = f"Se va a eliminar el grupo «{group.name}»."
    if count == 0:
        return f"{sentence} No tiene cuentas."
    accounts = "Su cuenta queda" if count == 1 else f"Sus {count} cuentas quedan"
    return f"{sentence} {accounts} sin grupo; no se elimina ninguna cuenta ni movimiento."


class AccountsPage(Page):
    """Net worth in pesos and dollars, then active and archived accounts.

    Active accounts are reordered by dragging their handle; the order is saved and shows
    in the sidebar and in every account list. Once there are groups, each one has its card
    with its subtotal, and the accounts in no group come last.
    """

    navigate_requested = Signal(object)  # PageId
    transactions_requested = Signal(object)  # TransactionFocus
    detail_requested = Signal(int)  # account id

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Cuentas")
        self._services = services
        self._event_bus = event_bus
        self.create_button = self.add_header_button("Agregar cuenta", primary=True)
        self.create_button.clicked.connect(lambda: self.open_account_dialog())
        self.create_group_button = self.add_header_button("Agregar grupo")
        self.create_group_button.clicked.connect(lambda: self.open_group_dialog())

        container = QWidget()
        page_layout = QVBoxLayout(container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(Space.L)
        # The net worth card lives as long as the page, so its figures count to new values.
        self.net_worth_card = NetWorthCard(services, theme_manager, compact=True)
        self.net_worth_card.set_amounts_hidden(services.settings.amounts_hidden())
        event_bus.amounts_hidden_changed.connect(self.net_worth_card.set_amounts_hidden)
        self.net_worth_card.currency_changed.connect(event_bus.net_worth_currency_changed)
        self.net_worth_card.rate_requested.connect(
            lambda: self.navigate_requested.emit(PageId.SETTINGS)
        )
        page_layout.addWidget(self.net_worth_card)
        self._sections = QVBoxLayout()
        self._sections.setSpacing(Space.L)
        # The active accounts, when there are enough to reorder: one list per group.
        self.account_list: ReorderableList | None = None
        self.account_lists: dict[int | None, ReorderableList] = {}
        self._group_ids: list[int] = []
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
            event_bus.net_worth_currency_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        clear_layout(self._sections)
        self.account_list = None
        self.account_lists = {}
        accounts = self._services.accounts.list_accounts(include_archived=True)
        self.net_worth_card.setVisible(bool(accounts))
        if not accounts:
            self._sections.addWidget(self._empty_state())
            return
        balances = self._services.accounts.balances()
        active = [a for a in accounts if not a.is_archived]
        archived = [a for a in accounts if a.is_archived]
        self.net_worth_card.show_day(date.today())
        if self._services.account_groups.list_groups():
            sections = self._services.account_groups.sections(active)
            self._group_ids = [s.group.id for s in sections if s.group is not None]
            for section in sections:
                self._sections.addWidget(self._group_card(section, balances))
        else:
            self._sections.addWidget(
                self._accounts_card("Cuentas activas", active, balances, reorderable=True)
            )
        if archived:
            self._sections.addWidget(self._accounts_card("Archivadas", archived, balances))

    def open_account_dialog(self, account: Account | None = None) -> None:
        AccountDialog(self._services, self._event_bus, account, parent=self.window()).exec()

    def open_group_dialog(self, group: AccountGroup | None = None) -> None:
        GroupDialog(self._services, self._event_bus, group, parent=self.window()).exec()

    def open_move_dialog(self, account: Account) -> None:
        MoveToGroupDialog(self._services, self._event_bus, account, parent=self.window()).exec()

    def open_goal_dialog(self, account: Account) -> None:
        """A new goal with ``account`` ticked, from the account's menu."""
        GoalDialog(self._services, self._event_bus, account=account, parent=self.window()).exec()

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
            card.body.addWidget(EmptyState("No hay cuentas activas.", compact=True))
        self._add_rows(card, accounts, balances, reorderable)
        return card

    def _group_card(self, section: AccountSection, balances: dict[int, Money]) -> Card:
        """A group's card: its name, its subtotal and its menu, then its accounts, which
        are reordered among themselves."""
        group = section.group
        card = Card()
        header = QHBoxLayout()
        header.setSpacing(Space.M)  # as in the rows, so the subtotal sits over their amounts
        header.setContentsMargins(0, 0, Space.S, 0)
        title = QLabel((group.name if group else "Sin grupo").upper())
        title.setObjectName("CardTitle")
        header.addWidget(title, stretch=1)
        total = self._services.account_groups.total(section.accounts, balances, date.today())
        text, tooltip = total_text(total, self._services.settings.amounts_hidden())
        subtotal = QLabel(text)
        subtotal.setObjectName("GroupTotal")
        subtotal.setToolTip(tooltip)
        header.addWidget(subtotal)
        if group is not None:
            header.addWidget(MoreButton(lambda: self.group_actions(group)))
        else:
            header.addSpacing(MoreButton.SIZE + header.spacing())
        # Room for the rows' «›», so the «⋯» of the group sits over theirs.
        chevron = QLabel("›")
        policy = chevron.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        chevron.setSizePolicy(policy)
        header.addWidget(chevron)
        chevron.hide()
        card.body.addLayout(header)
        if not section.accounts:
            card.body.addWidget(
                EmptyState("Sin cuentas. Usa «Mover a grupo…» en una cuenta.", compact=True)
            )
        list_key = group.id if group else None
        self._add_rows(
            card, section.accounts, balances, reorderable=True, key=list_key, aligned=True
        )
        return card

    def group_actions(self, group: AccountGroup) -> list[RowAction]:
        """Everything a group allows, for the «⋯» of its card."""
        group_ids = self._group_ids
        index = group_ids.index(group.id)
        return [
            RowAction("Renombrar", lambda: self.open_group_dialog(group), "pencil"),
            RowAction("Subir", lambda: self._move_group(group_ids, index, -1), enabled=index > 0),
            RowAction(
                "Bajar",
                lambda: self._move_group(group_ids, index, 1),
                enabled=index < len(group_ids) - 1,
            ),
            RowAction(
                "Eliminar grupo", lambda: self.delete_group(group), "trash", destructive=True
            ),
        ]

    def _move_group(self, group_ids: list[int], index: int, step: int) -> None:
        order = list(group_ids)
        order[index], order[index + step] = order[index + step], order[index]
        self._services.account_groups.reorder(order)
        self._event_bus.accounts_changed.emit()

    def delete_group(self, group: AccountGroup) -> None:
        count = self._services.account_groups.account_count(group.id)
        if confirm(self.window(), "Eliminar grupo", group_delete_warning(group, count)):
            self._services.account_groups.delete(group.id)
            self._event_bus.accounts_changed.emit()

    def _add_rows(
        self,
        card: Card,
        accounts: list[Account],
        balances: dict[int, Money],
        reorderable: bool,
        key: int | None = None,
        aligned: bool = False,
    ) -> None:
        """A row per account; ``reorderable`` gives each a drag handle once there is more
        than one, in a list kept in ``account_lists`` under ``key``. An ``aligned`` row
        without a handle keeps its room, to line up with the other groups' rows."""
        rows = None
        if reorderable and len(accounts) > 1:
            rows = ReorderableList()
            rows.order_changed.connect(self._save_order)
            self.account_lists[key] = rows
            self.account_list = self.account_list or rows
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
            row.detail_requested.connect(lambda account: self.detail_requested.emit(account.id))
            row.edit_requested.connect(self.open_account_dialog)
            row.value_update_requested.connect(self.open_value_dialog)
            row.move_requested.connect(self.open_move_dialog)
            row.goal_requested.connect(self.open_goal_dialog)
            row.archive_toggled.connect(self._toggle_archived)
            row.delete_requested.connect(self.delete_account)
            if rows is None:
                if aligned:
                    margins = row.layout().contentsMargins()
                    margins.setLeft(margins.left() + handle_indent())
                    row.layout().setContentsMargins(margins)
                card.body.addWidget(row)
            else:
                rows.add_row(account.id, row)

    def _save_order(self, account_ids: list[int]) -> None:
        self._services.accounts.reorder(account_ids)
        self._event_bus.accounts_changed.emit()

    def _toggle_archived(self, account: Account) -> None:
        self._services.accounts.set_archived(account.id, not account.is_archived)
        self._event_bus.accounts_changed.emit()

    def delete_account(self, account: Account) -> None:
        delete_account(self.window(), self._services, self._event_bus, account)

    def _empty_state(self) -> Card:
        card, state = empty_page_card(
            "Todavía no hay cuentas",
            "Una por cada lugar donde tengas dinero: banco, efectivo, dólares.",
            "Agregar cuenta",
            lambda: self.open_account_dialog(),
        )
        self.empty_create_button = state.action_button
        return card
