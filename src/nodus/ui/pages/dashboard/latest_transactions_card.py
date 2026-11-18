"""Inicio: the period's most recent movements."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.i18n import _
from nodus.models.period import Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.ui.text.formatting import format_date
from nodus.ui.theme.design import ControlSize, Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_rows import (
    TransactionListBuilder,
    TransactionListItem,
    delete_text,
    edit_text,
)
from nodus.ui.widgets.card import Card, card_header, see_all_link
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.elided_label import ElidedLabel
from nodus.ui.widgets.empty_state import NO_MOVEMENTS_TEXT, EmptyState
from nodus.ui.widgets.style import clear_layout, muted_label, set_style_property
from nodus.ui.widgets.tables.row_actions import Effect, RowAction, install_row_actions

LATEST_COUNT = 6
# With upcoming payments above it, the latest movements card gets shorter, so the right
# column stays as tall as the net worth card beside it.
LATEST_COUNT_BELOW_UPCOMING = 4


class LatestTransactionRow(QWidget):
    """A movement in the latest transactions card: what, where, how much and when. It
    answers as a row of Transacciones: a double click edits it, a right click shows its
    menu."""

    edit_requested = Signal(object)  # TransactionListItem
    delete_requested = Signal(object)  # TransactionListItem

    def __init__(self, item: TransactionListItem, transfer_color: str) -> None:
        super().__init__()
        self.item = item
        install_row_actions(self, self.actions)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.XS, Space.S, Space.XS)
        layout.setSpacing(Space.S)
        layout.addWidget(
            ColorDot(item.category_color or transfer_color, size=ControlSize.DOT_SMALL)
        )
        texts = QVBoxLayout()
        texts.setSpacing(0)
        title = ElidedLabel(item.description)
        title.setObjectName("RowTitle")
        subtitle = ElidedLabel(f"{item.category_name} · {item.account_text}")
        set_style_property(subtitle, "muted", True)
        texts.addWidget(title)
        texts.addWidget(subtitle)
        layout.addLayout(texts, stretch=1)
        figures = QVBoxLayout()
        figures.setSpacing(0)
        # One amount, so the name keeps its room; a transfer between currencies tells
        # what arrived under the mouse, and the accounts it went between below its name.
        amount = QLabel(item.short_amount_text)
        if item.short_amount_text != item.amount_text:
            amount.setToolTip(item.amount_text)
        amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        set_style_property(amount, "tone", item.tone)
        day = muted_label(format_date(item.occurred_on))
        day.setAlignment(Qt.AlignmentFlag.AlignRight)
        figures.addWidget(amount)
        figures.addWidget(day)
        layout.addLayout(figures)

    def actions(self) -> list[RowAction]:
        """The same menu as its row in Transacciones."""
        return [
            RowAction(
                edit_text(self.item.transaction),
                lambda: self.edit_requested.emit(self.item),
                "pencil",
                default=True,
                effect=Effect.OPEN,
            ),
            RowAction(
                delete_text(self.item.transaction),
                lambda: self.delete_requested.emit(self.item),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]


class LatestTransactionsCard(Card):
    """The period's most recent movements and a link to see them all."""

    see_all_requested = Signal()
    edit_requested = Signal(object)  # TransactionListItem
    delete_requested = Signal(object)  # TransactionListItem

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._theme_manager = theme_manager
        self._builder = TransactionListBuilder(services)
        header = card_header(self, _("Últimas transacciones"))
        self.see_all_button = see_all_link(header, _("Ver todas"), self.see_all_requested)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(0)
        self.body.addLayout(self._rows)
        self.body.addStretch()

    def show_period(self, period: Period, count: int = LATEST_COUNT) -> None:
        clear_layout(self._rows)
        # Extra rows leave room for transfers, whose two legs become one item.
        # Only what already happened: installments still to come are not the latest.
        end = min(period.end, date.today())
        transactions = self._services.transactions.list_transactions(
            TransactionFilter(start=period.start, end=end, limit=count * 2)
        )
        items = self._builder.build(transactions)[:count]
        if not items:
            self._rows.addWidget(EmptyState(_(NO_MOVEMENTS_TEXT), compact=True))
        transfer_color = self._theme_manager.theme.text_muted
        for item in items:
            row = LatestTransactionRow(item, transfer_color)
            row.edit_requested.connect(self.edit_requested)
            row.delete_requested.connect(self.delete_requested)
            self._rows.addWidget(row)
