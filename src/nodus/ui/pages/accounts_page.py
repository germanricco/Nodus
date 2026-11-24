"""Accounts section: net worth summary and the list of accounts."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from nodus.i18n import _, ngettext
from nodus.models.account import Account
from nodus.models.account_group import AccountGroup
from nodus.models.money import Money
from nodus.services.accounts.account_group_service import AccountSection
from nodus.services.container import Services
from nodus.ui.actions.accounts import delete_account, edit_account, toggle_account_archived
from nodus.ui.dialogs.account_group_dialogs import GroupDialog, MoveToGroupDialog
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.dialogs.goal_dialog import GoalDialog
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, PageId, history_focus
from nodus.ui.pages.base.net_worth_card import NetWorthCard
from nodus.ui.pages.base.page import Page
from nodus.ui.text.formatting import signed
from nodus.ui.text.labels import ACCOUNT_TYPE_LABELS
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.undo import offer_undo
from nodus.ui.widgets.card import Card, card_title
from nodus.ui.widgets.empty_state import EmptyState, empty_page_card
from nodus.ui.widgets.money_label import MoneyLabel, masked, total_text
from nodus.ui.widgets.style import clear_layout, muted_label
from nodus.ui.widgets.tables.reorderable_list import ReorderableList
from nodus.ui.widgets.tables.row_actions import (
    Effect,
    MoreButton,
    RowAction,
    install_row_actions,
    open_cue,
)

# The lists of the groups' cards, which take each other's accounts.
ACCOUNTS_FAMILY = "accounts"


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
        details = [_(ACCOUNT_TYPE_LABELS[account.type]), account.currency.value]
        if value_change is not None and not value_change.is_zero:
            change = masked(value_change) if hide_balance else signed(value_change)
            details.append(_("Rendimiento {amount}").format(amount=change))
        subtitle = muted_label(" · ".join(details))
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
        layout.addWidget(open_cue())
        install_row_actions(self, self.actions, open_on_click=DetailId.ACCOUNT.open_text)

    @property
    def can_update_value(self) -> bool:
        """Savings and investments change value by themselves, until they are archived."""
        return self.account.type.changes_value and not self.account.is_archived

    def actions(self) -> list[RowAction]:
        """Everything the account allows, for the «⋯» and the right click."""
        account = self.account
        result = [
            RowAction(
                _("Abrir"),
                lambda: self.detail_requested.emit(account),
                default=True,
                effect=Effect.OPEN,
            ),
            RowAction(
                _("Ver movimientos"),
                lambda: self.transactions_requested.emit(account),
                "list",
                enabled=self.has_movements,
                effect=Effect.OPEN,
            ),
        ]
        if self.can_update_value:
            result.append(
                RowAction(
                    _("Actualizar valor"),
                    lambda: self.value_update_requested.emit(account),
                    "trend",
                    effect=Effect.OPEN,
                )
            )
        if self.can_update_value:  # what a savings goal is filled with
            result.append(
                RowAction(
                    _("Usar en una meta…"),
                    lambda: self.goal_requested.emit(account),
                    "goal",
                    effect=Effect.OPEN,
                )
            )
        result.append(
            RowAction(
                _("Editar"), lambda: self.edit_requested.emit(account), "pencil", effect=Effect.OPEN
            )
        )
        if not account.is_archived:  # archived accounts show apart from every group
            result.append(
                RowAction(
                    _("Mover a grupo…"),
                    lambda: self.move_requested.emit(account),
                    "folder",
                    effect=Effect.OPEN,
                )
            )
        return result + [
            RowAction(
                _("Desarchivar") if account.is_archived else _("Archivar"),
                lambda: self.archive_toggled.emit(account),
                "archive",
                effect=Effect.TOGGLE,
            ),
            RowAction(
                _("Eliminar"),
                lambda: self.delete_requested.emit(account),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]


def group_delete_warning(group: AccountGroup, count: int) -> str:
    """What deleting ``group`` does: its accounts stay, in no group."""
    if count == 0:
        return _("Se va a eliminar el grupo «{name}». No tiene cuentas.").format(name=group.name)
    return ngettext(
        "Se va a eliminar el grupo «{name}». Su cuenta queda sin grupo; no se elimina "
        "ninguna cuenta ni movimiento.",
        "Se va a eliminar el grupo «{name}». Sus {count} cuentas quedan sin grupo; no se "
        "elimina ninguna cuenta ni movimiento.",
        count,
    ).format(name=group.name, count=count)


class AccountsPage(Page):
    """Net worth in pesos and dollars, then active and archived accounts.

    Active accounts are reordered by dragging their handle; the order is saved and shows
    in the sidebar and in every account list. Once there are groups, each one has its card
    with its subtotal, and the accounts in no group come last; dragging an account to
    another group's card moves it there, with «Deshacer».
    """

    navigate_requested = Signal(object)  # PageId
    transactions_requested = Signal(object)  # TransactionFocus
    detail_requested = Signal(int)  # account id

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(PageId.ACCOUNTS.label)
        self._services = services
        self._event_bus = event_bus
        self.create_button = self.add_header_button(_("Agregar cuenta"), primary=True)
        self.create_button.clicked.connect(lambda: self.open_account_dialog())
        self.create_group_button = self.add_header_button(_("Agregar grupo"))
        self.create_group_button.clicked.connect(lambda: self.open_group_dialog())

        page_layout = self.scrolling_body()
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
                self._accounts_card(_("Cuentas activas"), active, balances, reorderable=True)
            )
        if archived:
            self._sections.addWidget(self._accounts_card(_("Archivadas"), archived, balances))

    def open_account_dialog(self, account: Account | None = None) -> None:
        edit_account(self, self._services, self._event_bus, account)

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
            card.body.addWidget(EmptyState(_("No hay cuentas activas."), compact=True))
        self._add_rows(card, accounts, balances, reorderable)
        return card

    def _group_card(self, section: AccountSection, balances: dict[int, Money]) -> Card:
        """A group's card: its name, its subtotal and its menu, then its accounts, which
        are reordered among themselves and dragged to other groups."""
        group = section.group
        card = Card()
        header = QHBoxLayout()
        header.setSpacing(Space.M)  # as in the rows, so the subtotal sits over their amounts
        header.setContentsMargins(0, 0, Space.S, 0)
        title = card_title(group.name if group else _("Sin grupo"))
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
        group_id = group.id if group else None
        rows = self._add_rows(
            card, section.accounts, balances, reorderable=True, key=group_id, family=ACCOUNTS_FAMILY
        )
        rows.set_placeholder(_("Sin cuentas. Arrastra una aquí o usa «Mover a grupo…»."))
        rows.row_received.connect(
            lambda account_id, gap: self._place_account(account_id, group_id, gap)
        )
        return card

    def group_actions(self, group: AccountGroup) -> list[RowAction]:
        """Everything a group allows, for the «⋯» of its card."""
        group_ids = self._group_ids
        index = group_ids.index(group.id)
        return [
            RowAction(
                _("Renombrar"), lambda: self.open_group_dialog(group), "pencil", effect=Effect.OPEN
            ),
            RowAction(
                _("Subir"),
                lambda: self._move_group(group_ids, index, -1),
                enabled=index > 0,
                effect=Effect.TOGGLE,
            ),
            RowAction(
                _("Bajar"),
                lambda: self._move_group(group_ids, index, 1),
                enabled=index < len(group_ids) - 1,
                effect=Effect.TOGGLE,
            ),
            RowAction(
                _("Eliminar grupo"),
                lambda: self.delete_group(group),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]

    def _move_group(self, group_ids: list[int], index: int, step: int) -> None:
        order = list(group_ids)
        order[index], order[index + step] = order[index + step], order[index]
        self._services.account_groups.reorder(order)
        self._event_bus.accounts_changed.emit()

    def delete_group(self, group: AccountGroup) -> None:
        count = self._services.account_groups.account_count(group.id)
        delete_with_confirm(
            self.window(),
            _("Eliminar grupo"),
            group_delete_warning(group, count),
            lambda: self._services.account_groups.delete(group.id),
            self._event_bus.accounts_changed,
        )

    def _add_rows(
        self,
        card: Card,
        accounts: list[Account],
        balances: dict[int, Money],
        reorderable: bool,
        key: int | None = None,
        family: str | None = None,
    ) -> ReorderableList | None:
        """A row per account. ``reorderable`` gives each a drag handle, in a list kept in
        ``account_lists`` under ``key``, once there is more than one account; with a
        ``family`` (a group's card) always, since its rows also go to the other groups."""
        rows = None
        if reorderable and (len(accounts) > 1 or family is not None):
            rows = ReorderableList(family=family)
            rows.order_changed.connect(self._save_order)
            self.account_lists[key] = rows
            self.account_list = self.account_list or rows
            card.body.addWidget(rows)
        for account in accounts:
            gain = self._services.accounts.value_gain(account, balances[account.id])
            value_change = gain.amount if gain else None
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
            row.delete_requested.connect(self._delete_account)
            if rows is None:
                card.body.addWidget(row)
            else:
                rows.add_row(account.id, row)
        return rows

    def _save_order(self, account_ids: list[int]) -> None:
        self._services.accounts.reorder(account_ids)
        self._event_bus.accounts_changed.emit()

    def _place_account(self, account_id: int, group_id: int | None, gap: int) -> None:
        """An account dropped on another group's card, at ``gap``."""
        self._services.account_groups.place_account(account_id, group_id, gap)
        self._event_bus.accounts_changed.emit()
        offer_undo(self, self._services, self._event_bus.accounts_changed)

    def _toggle_archived(self, account: Account) -> None:
        toggle_account_archived(self._services, self._event_bus, account)

    def _delete_account(self, account: Account) -> None:
        delete_account(self.window(), self._services, self._event_bus, account)

    def _empty_state(self) -> Card:
        card, state = empty_page_card(
            _("Todavía no hay cuentas"),
            _("Una por cada lugar donde tengas dinero: banco, efectivo, dólares."),
            _("Agregar cuenta"),
            lambda: self.open_account_dialog(),
        )
        self.empty_create_button = state.action_button
        return card
