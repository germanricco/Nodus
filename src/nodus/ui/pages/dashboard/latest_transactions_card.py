"""Inicio: the period's most recent movements."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal

from nodus.i18n import _
from nodus.models.period import Period
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_rows import (
    TransactionListBuilder,
    TransactionListItem,
    delete_text,
    edit_text,
)
from nodus.ui.widgets.card import Card, card_header, see_all_link
from nodus.ui.widgets.empty_state import NO_MOVEMENTS_TEXT, EmptyState
from nodus.ui.widgets.style import clear_layout
from nodus.ui.widgets.tables.row_actions import Effect, RowAction
from nodus.ui.widgets.tables.row_layout import row_list
from nodus.ui.widgets.tables.transaction_table import CompactMovementRow, TransactionTableModel

LATEST_COUNT = 6
# With upcoming payments above it, the latest movements card gets shorter, so the right
# column stays as tall as the net worth card beside it.
LATEST_COUNT_BELOW_UPCOMING = 4


class LatestTransactionsCard(Card):
    """The period's most recent movements and a link to see them all. Each row is drawn
    as Transacciones draws it (``CompactMovementRow``), with the date under the amount,
    and answers the same way: a double click edits it, a right click shows its menu."""

    see_all_requested = Signal()
    edit_requested = Signal(object)  # TransactionListItem
    delete_requested = Signal(object)  # TransactionListItem

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__()
        self._services = services
        self._theme_manager = theme_manager
        self._builder = TransactionListBuilder(services)
        self.model = TransactionTableModel(theme_manager.theme, date_under_amount=True)
        theme_manager.theme_changed.connect(self.model.set_theme)
        header = card_header(self, _("Últimas transacciones"))
        self.see_all_button = see_all_link(header, _("Ver todas"), self.see_all_requested)
        self._rows = row_list()
        self.body.addLayout(self._rows)
        self.body.addStretch()

    def show_period(self, period: Period, count: int = LATEST_COUNT) -> None:
        clear_layout(self._rows)
        # Extra rows leave room for transfers, whose two legs become one item.
        # Only what already happened: installments still to come are not the latest. Only
        # the user's own: Home is about their money.
        end = min(period.end, date.today())
        transactions = self._services.transactions.list_transactions(
            TransactionFilter(start=period.start, end=end, limit=count * 2, own_only=True)
        )
        self.model.set_items(self._builder.build(transactions)[:count])
        if not self.model.rowCount():
            self._rows.addWidget(EmptyState(_(NO_MOVEMENTS_TEXT), compact=True))
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            self._rows.addWidget(
                CompactMovementRow(self.model, row, lambda item=item: self.actions(item))
            )

    def rows(self) -> list[CompactMovementRow]:
        return [
            widget
            for index in range(self._rows.count())
            if isinstance(widget := self._rows.itemAt(index).widget(), CompactMovementRow)
        ]

    def actions(self, item: TransactionListItem) -> list[RowAction]:
        """The same menu as its row in Transacciones."""
        return [
            RowAction(
                edit_text(item.transaction),
                lambda: self.edit_requested.emit(item),
                "pencil",
                default=True,
                effect=Effect.OPEN,
            ),
            RowAction(
                delete_text(item.transaction),
                lambda: self.delete_requested.emit(item),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]
