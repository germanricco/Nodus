"""The table of movements with its actions, shared by Transacciones and the detail pages."""

from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QHeaderView

from nodus.i18n import _
from nodus.models.money import Money
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.reports.dashboard_service import FilteredTotals
from nodus.ui.actions.transactions import delete_transactions, edit_transaction, pay_off_actions
from nodus.ui.dialogs.bulk_edit_dialog import BulkEditDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.pages.base.page import Page
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
from nodus.ui.widgets.style import hint_label
from nodus.ui.widgets.tables.row_actions import Effect, RowAction
from nodus.ui.widgets.tables.selectable_table import SelectableTable
from nodus.ui.widgets.tables.selection_bar import SelectionBar
from nodus.ui.widgets.tables.table import DELETE_KEY_HINT, bind_delete_key
from nodus.ui.widgets.tables.transaction_table import (
    ACCOUNT,
    CATEGORY,
    DESCRIPTION,
    PAYEE,
    TAGS,
    TransactionTableModel,
)

# Columns that fit their content only up to these widths, so the description keeps room
# on a laptop screen; longer names end in "…" and show whole in a wider window.
MAX_COLUMN_WIDTHS = {PAYEE: 110, CATEGORY: 140, TAGS: 120, ACCOUNT: 110}


def totals_text(count: int, totals: FilteredTotals) -> str:
    """The foot of the list: "24 movimientos · Ingresos $ … · Gastos $ … · Neto $ …"."""
    parts = [movements_text(count)]
    sums = selection_totals_text(totals)
    if count and sums:
        parts.append(sums)
    if totals.unconverted:
        parts.append(unconverted_note(totals.unconverted))
    return " · ".join(parts)


def selection_totals_text(totals: FilteredTotals) -> str:
    """What some movements add up to: "Ingresos $ … · Gastos $ … · Neto $ …"."""
    if not (totals.income.cents or totals.expenses.cents):
        return ""
    return " · ".join(
        [
            _("Ingresos {amount}").format(amount=totals.income.format()),
            _("Gastos {amount}").format(amount=totals.expenses.format()),
            _("Neto {amount}").format(amount=totals.net.format()),
        ]
    )


def selection_totals_html(totals: FilteredTotals, theme: Theme) -> str:
    """``selection_totals_text`` with income in green, expenses in red and the net by its
    sign, as amounts look everywhere else."""
    if not (totals.income.cents or totals.expenses.cents):
        return ""

    def part(text: str, money: Money, color: str) -> str:
        """``text`` with its ``{amount}`` in ``color``."""
        amount = escape(money.format())
        return escape(text).replace("{amount}", f'<span style="color:{color}">{amount}</span>')

    return " · ".join(
        [
            part(_("Ingresos {amount}"), totals.income, theme.income),
            part(_("Gastos {amount}"), totals.expenses, theme.expense),
            part(_("Neto {amount}"), totals.net, theme.amount_color(totals.net)),
        ]
    )


class TransactionListView(Card):
    """Movements, newest first, with what they add up to at the foot and an
    ``empty_state`` when there are none.

    Double-clicking a row edits it; its «⋯» or a right click offers every action, and
    several rows can be chosen to edit or delete them together, from a selection bar that
    takes the place of ``page``'s header. A transfer shows as one row for both legs.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        theme_manager: ThemeManager,
        page: Page,
    ) -> None:
        super().__init__()
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self._page = page
        self._builder = TransactionListBuilder(services)

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

        self.model = TransactionTableModel(theme_manager.theme)
        self.table = SelectableTable(self.model, DESCRIPTION, self.row_actions)
        bind_delete_key(self.table, self.delete_selected)
        self.table.selection_changed.connect(self._update_actions)
        self.empty_state = EmptyState()
        self.totals_label = hint_label()
        self.totals_label.setContentsMargins(Space.S, Space.XS, Space.S, 0)
        self.body.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        self.body.addWidget(self.table)
        self.body.addWidget(self.empty_state, stretch=1)
        self.body.addWidget(self.totals_label)
        theme_manager.theme_changed.connect(self.model.set_theme)

    def show_matching(self, criteria: TransactionFilter) -> bool:
        """Lists the movements matching ``criteria``; False when there are none, so the
        caller can say why in ``empty_state``."""
        transactions = self._services.transactions.list_transactions(criteria)
        items = self._builder.build(transactions)
        self.model.set_items(items)
        # Whoever does not use tags keeps the room for the description.
        self.table.setColumnHidden(TAGS, not any(item.tags for item in items))
        self._fit_columns()
        has_rows = self.model.rowCount() > 0
        self.totals_label.setText(
            totals_text(self.model.rowCount(), self._services.dashboard.totals(criteria))
        )
        self.totals_label.setVisible(has_rows)
        self.table.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)
        self._update_actions()
        return has_rows

    def selected_items(self) -> list[TransactionListItem]:
        return [self.model.item(row) for row in self.table.selected_rows()]

    def row_actions(self, row: int) -> list[RowAction]:
        """The menu of a row: edit it and delete it; an installment, its whole purchase,
        which can also be paid off early."""
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
            *pay_off_actions(self, self._services, self._event_bus, item),
            RowAction(
                delete_text(transaction),
                lambda: self.delete([item]),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            ),
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

    def _fit_columns(self) -> None:
        header = self.table.horizontalHeader()
        for column, max_width in MAX_COLUMN_WIDTHS.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(column, min(self.table.sizeHintForColumn(column), max_width))

    def _update_actions(self) -> None:
        """With two or more rows chosen, the page's header becomes the selection bar, with
        what they add up to."""
        items = self.selected_items()
        several = len(items) > 1
        self._page.show_selection_bar(several)
        if not several:
            return
        totals = self._services.dashboard.totals_of([item.transaction for item in items])
        self.selection_bar.set_count(
            len(items), selection_totals_html(totals, self._theme_manager.theme)
        )
