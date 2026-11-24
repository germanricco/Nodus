"""The table of movements with its actions, shared by Transacciones and the detail pages."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSizePolicy

from nodus.i18n import _
from nodus.models.money import Money
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.reports.dashboard_service import FilteredTotals
from nodus.ui.actions.transactions import delete_transactions, edit_transaction, pay_off_actions
from nodus.ui.dialogs.bulk_edit_dialog import BulkEditDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import RecordLink
from nodus.ui.pages.base.page import Page
from nodus.ui.text.formatting import signed
from nodus.ui.text.labels import movements_text, unconverted_note
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_rows import (
    TransactionListBuilder,
    TransactionListItem,
    delete_text,
    edit_text,
)
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.tables.row_actions import Effect, RowAction
from nodus.ui.widgets.tables.selectable_table import SelectableTable
from nodus.ui.widgets.tables.selection_bar import SelectionBar
from nodus.ui.widgets.tables.table import DELETE_KEY_HINT, bind_delete_key
from nodus.ui.widgets.tables.transaction_table import (
    DATE,
    MOVEMENT,
    Omit,
    TransactionTableModel,
    show_movements,
)


def summary_html(caption: str, count: int, totals: FilteredTotals, theme: Theme) -> str:
    """What the list shows, over it: "Noviembre 2026 · 12 movimientos · Entró … · Salió …
    · Neto …", led by ``caption`` when there is one. The numbers are those of
    ``FilteredTotals``: no transfers, and refunds take off from spending."""
    parts = [f"<b>{escape(caption)}</b>"] if caption else []
    parts.append(escape(movements_text(count)))
    figures = totals_html(totals, theme)
    if count and figures:
        parts.append(figures)
    if totals.unconverted:
        parts.append(escape(unconverted_note(totals.unconverted)))
    return " · ".join(parts)


def totals_html(totals: FilteredTotals, theme: Theme) -> str:
    """What came in, what went out and the net, each signed and in its color; only the
    net when there is just one of the two, as for a filter of one category. Empty when
    there is neither."""
    if not (totals.income.cents or totals.expenses.cents):
        return ""

    def colored(money: Money) -> str:
        return f'<span style="color:{theme.amount_color(money)}">{escape(signed(money))}</span>'

    if not (totals.income.cents and totals.expenses.cents):
        return colored(totals.net)
    return " · ".join(
        escape(text).replace("{amount}", colored(money))
        for text, money in (
            (_("Entró {amount}"), totals.income),
            (_("Salió {amount}"), -totals.expenses),
            (_("Neto {amount}"), totals.net),
        )
    )


class TransactionListView(Card):
    """Movements, newest first or in the order of the column clicked, with what they add
    up to over them and an ``empty_state`` when there are none.

    Double-clicking a row edits it; its «⋯» or a right click offers every action, and
    several rows can be chosen to edit or delete them together, from a selection bar that
    takes the place of ``page``'s header and says what they add up to. A transfer shows
    as one row for both legs. On a payee's or an account's page, ``omit`` leaves out of
    each row what the whole page is about.
    """

    record_requested = Signal(object)  # RecordLink

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        theme_manager: ThemeManager,
        page: Page,
        omit: Omit | None = None,
    ) -> None:
        super().__init__()
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self._page = page
        self._omit = omit
        self._builder = TransactionListBuilder(services)
        self._caption = ""
        self._totals: FilteredTotals | None = None

        self.selection_bar = SelectionBar(_("seleccionadas"))
        self.edit_button = self.selection_bar.add_action(_("Editar…"), self.edit_selected)
        self.edit_button.setToolTip(
            _("Cambia la categoría, el beneficiario, la nota o las etiquetas")
        )
        self.delete_button = self.selection_bar.add_action(
            _("Eliminar"), self.delete_selected, destructive=True
        )
        self.delete_button.setToolTip(_(DELETE_KEY_HINT))
        self.selection_bar.cleared.connect(lambda: self.table.clearSelection())
        page.set_selection_bar(self.selection_bar)

        self.model = TransactionTableModel(theme_manager.theme, omit)
        self.table = SelectableTable(self.model, MOVEMENT, self.row_actions)
        show_movements(self.table)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(DATE, Qt.SortOrder.DescendingOrder)
        bind_delete_key(self.table, self.delete_selected)
        self.table.selection_changed.connect(self._update_actions)
        self.empty_state = EmptyState()
        # Over the list, where it is read before scrolling (plan 029a, 5.5).
        self.summary_label = QLabel()
        self.summary_label.setObjectName("ListSummary")
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_label.setWordWrap(True)
        self.summary_label.setContentsMargins(Space.S, Space.XS, Space.S, Space.S)
        self.body.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        self.body.addWidget(self.summary_label)
        self.body.addWidget(self.table)
        self.body.addWidget(self.empty_state, stretch=1)
        self._rows_height: int | None = None
        theme_manager.theme_changed.connect(self.model.set_theme)
        theme_manager.theme_changed.connect(self._show_summary)
        theme_manager.theme_changed.connect(self._update_actions)

    def show_matching(self, criteria: TransactionFilter, caption: str = "") -> bool:
        """Lists the movements matching ``criteria``, under a summary led by ``caption``
        (what they are: the period and its filters); False when there are none, so the
        caller can say why in ``empty_state``."""
        transactions = self._services.transactions.list_transactions(criteria)
        self.model.set_items(self._builder.build(transactions))
        self._caption = caption
        self._totals = self._services.dashboard.totals(criteria)
        self._show_summary()
        has_rows = self.model.rowCount() > 0
        self.summary_label.setVisible(has_rows)
        self.table.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)
        self._fit_height(has_rows)
        self._update_actions()
        return has_rows

    def keep_height(self, rows_height: int) -> None:
        """On a record's page: at least ``rows_height`` tall with movements, and only as
        tall as its message without them, so an empty list does not fill the page."""
        self._rows_height = rows_height
        self._fit_height(self.table.isVisibleTo(self))

    def _fit_height(self, has_rows: bool) -> None:
        if self._rows_height is None:
            return  # the list is the page: it fills it, with movements or not
        self.setMinimumHeight(self._rows_height if has_rows else 0)
        vertical = QSizePolicy.Policy.Expanding if has_rows else QSizePolicy.Policy.Maximum
        self.setSizePolicy(QSizePolicy.Policy.Preferred, vertical)

    def selected_items(self) -> list[TransactionListItem]:
        return [self.model.item(row) for row in self.table.selected_rows()]

    def row_actions(self, row: int) -> list[RowAction]:
        """The menu of a row: edit it, open its payee's page and delete it; an
        installment, its whole purchase, which can also be paid off early."""
        item = self.model.item(row)
        transaction = item.transaction
        return [
            RowAction(
                edit_text(transaction),
                lambda: self.edit(item),
                "pencil",
                default=True,
                effect=Effect.OPEN,
            ),
            *self._payee_actions(item),
            *pay_off_actions(self, self._services, self._event_bus, item),
            RowAction(
                delete_text(transaction),
                lambda: self.delete([item]),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
        ]

    def _payee_actions(self, item: TransactionListItem) -> list[RowAction]:
        """«Ver beneficiario», unless the row has none or the page is already its."""
        payee_id = item.transaction.payee_id
        if payee_id is None or self._omit is Omit.PAYEE:
            return []
        return [
            RowAction(
                _("Ver beneficiario"),
                lambda: self.record_requested.emit(RecordLink.payee(payee_id)),
                "payee",
                effect=Effect.OPEN,
            )
        ]

    def edit(self, item: TransactionListItem) -> None:
        edit_transaction(self._services, self._event_bus, self._theme_manager, item, self.window())

    def delete_selected(self) -> None:
        self.delete(self.selected_items())

    def delete(self, items: list[TransactionListItem]) -> None:
        delete_transactions(self._services, self._event_bus, items, self.window())

    def edit_selected(self) -> None:
        """Edits the chosen rows together: their category, payee, note or tags."""
        items = self.selected_items()
        if items:
            BulkEditDialog(
                self._services,
                self._event_bus,
                [item.transaction for item in items],
                parent=self.window(),
            ).exec()

    def _show_summary(self) -> None:
        if self._totals is not None:
            self.summary_label.setText(
                summary_html(
                    self._caption,
                    self.model.rowCount(),
                    self._totals,
                    self._theme_manager.theme,
                )
            )

    def _update_actions(self) -> None:
        """With two or more rows chosen, the page's header becomes the selection bar, with
        what they add up to."""
        items = self.selected_items()
        several = len(items) > 1
        self._page.show_selection_bar(several)
        if not several:
            return
        totals = self._services.dashboard.totals_of([item.transaction for item in items])
        self.selection_bar.set_count(len(items), totals_html(totals, self._theme_manager.theme))
