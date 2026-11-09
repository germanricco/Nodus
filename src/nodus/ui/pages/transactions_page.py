"""Transactions section: every movement of a month, with filters."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
)

from nodus.models.period import Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.dashboard_service import FilteredTotals
from nodus.ui.dialogs.change_category_dialog import ChangeCategoryDialog
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.export import export_transactions
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.labels import movements_text, transactions_text, unconverted_note
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder, TransactionListItem
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.row_actions import RowAction
from nodus.ui.widgets.selectable_table import SelectableTable
from nodus.ui.widgets.selection_bar import SelectionBar
from nodus.ui.widgets.selectors import (
    AccountComboBox,
    CategoryComboBox,
    PayeeComboBox,
    TagComboBox,
)
from nodus.ui.widgets.style import set_style_property
from nodus.ui.widgets.table import DELETE_KEY_HINT, bind_delete_key
from nodus.ui.widgets.transaction_table import (
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

# Type filter: label -> (transaction type, is_transfer, refund_linked) criteria.
TYPE_FILTERS = {
    "Tipo": (None, None, None),
    "Gastos": (TransactionType.EXPENSE, False, None),
    "Ingresos": (TransactionType.INCOME, False, None),
    "Transferencias": (None, True, None),
    "Reembolsos": (None, False, True),
}


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
            f"Ingresos {totals.income.format()}",
            f"Gastos {totals.expenses.format()}",
            f"Neto {totals.net.format()}",
        ]
    )


def common_kind(items: list[TransactionListItem]) -> TransactionType | None:
    """The type ``items`` share when they are all expenses or all incomes, so they can
    move to one category; None with a transfer or a mix."""
    kinds = {item.transaction.type for item in items}
    if not items or any(item.is_transfer for item in items) or len(kinds) != 1:
        return None
    return kinds.pop()


def export_filename(period: Period) -> str:
    """ "nodus-transacciones-2026-11.csv" for a month, start and end dates otherwise."""
    if period.is_whole_months and period.first_month == period.last_month:
        return f"nodus-transacciones-{period.start:%Y-%m}.csv"
    return f"nodus-transacciones-{period.start:%Y-%m-%d}_{period.end:%Y-%m-%d}.csv"


class TransactionsPage(Page):
    """The movements of a period, newest first, narrowed by account, category, payee, tag,
    type or text, with what they add up to at the foot.

    Double-clicking a row edits it; its «⋯» or a right click offers every action, and
    several rows can be chosen to change their category or delete them together. A
    transfer shows as one row for both of its legs. Each list filter ends with «Editar»,
    which asks for the page that manages that list.
    """

    navigate_requested = Signal(object)  # PageId

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Transacciones")
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager
        self._builder = TransactionListBuilder(services)

        # The period goes in the header, as on the dashboard, to leave the row to the filters.
        self.period_selector = PeriodSelector()
        self.add_header_widget(self.period_selector)
        self.export_button = self.add_header_button("Exportar")
        self.export_button.setToolTip("Guarda en un archivo CSV los movimientos que se ven")
        self.export_button.clicked.connect(self.export_shown)
        self.selection_bar = SelectionBar("seleccionadas")
        self.category_button = self.selection_bar.add_action(
            "Cambiar categoría", self.change_category_of_selected
        )
        self.delete_button = self.selection_bar.add_action("Eliminar", self.delete_selected)
        self.delete_button.setToolTip(DELETE_KEY_HINT)
        self.selection_bar.cleared.connect(lambda: self.table.clearSelection())
        self.set_selection_bar(self.selection_bar)

        self.account_filter = AccountComboBox()
        self.category_filter = CategoryComboBox()
        self.payee_filter = PayeeComboBox()
        self.tag_filter = TagComboBox()
        for combo, page_id in (
            (self.account_filter, PageId.ACCOUNTS),
            (self.category_filter, PageId.CATEGORIES),
            (self.payee_filter, PageId.PAYEES),
            (self.tag_filter, PageId.TAGS),
        ):
            combo.enable_manage_item()
            combo.manage_requested.connect(partial(self.navigate_requested.emit, page_id))
        self.type_filter = QComboBox()
        self.type_filter.addItems(list(TYPE_FILTERS))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar…")
        self.search_input.setToolTip(
            "Busca en la nota y en los nombres del beneficiario y las etiquetas"
        )
        self.search_input.setMinimumWidth(140)
        self.search_input.setClearButtonEnabled(True)
        self.clear_filters_button = QPushButton("Limpiar filtros")
        self.clear_filters_button.setObjectName("SecondaryButton")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        for widget in self._filter_combos():
            filters.addWidget(widget)
        filters.addWidget(self.search_input, stretch=1)
        filters.addWidget(self.clear_filters_button)
        self.content_layout.addLayout(filters)

        self.model = TransactionTableModel(theme_manager.theme)
        self.table = self._build_table()
        self.empty_label = QLabel("Sin transacciones con estos filtros")
        self.empty_label.setObjectName("EmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = Card()
        card.body.setContentsMargins(8, 8, 8, 8)
        card.body.addWidget(self.table)
        card.body.addWidget(self.empty_label, stretch=1)
        self.totals_label = QLabel()
        self.totals_label.setObjectName("FieldHint")
        self.totals_label.setContentsMargins(8, 4, 8, 0)
        card.body.addWidget(self.totals_label)
        self.content_layout.addWidget(card, stretch=1)

        self.period_selector.period_changed.connect(self.reload)
        self.account_filter.currentIndexChanged.connect(self.reload)
        self.category_filter.currentIndexChanged.connect(self.reload)
        self.payee_filter.currentIndexChanged.connect(self.reload)
        self.tag_filter.currentIndexChanged.connect(self.reload)
        self.type_filter.currentIndexChanged.connect(self.reload)
        self.search_input.textChanged.connect(self.reload)
        theme_manager.theme_changed.connect(self.model.set_theme)
        for signal in (
            event_bus.transactions_changed,
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.payees_changed,
            event_bus.tags_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        """Reloads the filter choices (keeping the selection) and then the movements."""
        self._load_filter_choices()
        self.reload()

    def _load_filter_choices(self) -> None:
        self.account_filter.set_accounts(
            self._services.accounts.list_accounts(include_archived=True), "Cuenta"
        )
        categories = self._services.categories
        self.category_filter.set_categories(
            [
                ("Gastos", categories.category_tree(TransactionType.EXPENSE)),
                ("Ingresos", categories.category_tree(TransactionType.INCOME)),
            ],
            "Categoría",
        )
        self.payee_filter.set_payees(self._services.payees.list_payees(), "Beneficiario")
        self.tag_filter.set_tags(self._services.tags.list_tags(), "Etiqueta")

    def reload(self) -> None:
        """Lists the movements matching the current filters."""
        criteria = self.current_filter()
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
        self.empty_label.setVisible(not has_rows)
        self._update_actions()
        self.clear_filters_button.setEnabled(self._has_filters())
        for combo in self._filter_combos():
            set_style_property(combo, "filter", "active" if combo.currentIndex() > 0 else "idle")

    def clear_filters(self) -> None:
        """Back to every movement of the period shown; the period itself is kept."""
        self._reset_filters()
        self.reload()

    def focus(self, focus: TransactionFocus) -> None:
        """Shows the period of ``focus`` with only its account, category, payee or tag
        filtered, as other pages ask for.

        Does not reload: the caller shows the page, which refreshes it.
        """
        self._load_filter_choices()
        self._reset_filters()
        self.period_selector.blockSignals(True)
        self.period_selector.set_period(focus.period)
        self.period_selector.blockSignals(False)
        for combo, item_id in (
            (self.account_filter, focus.account_id),
            (self.category_filter, focus.category_id),
            (self.payee_filter, focus.payee_id),
            (self.tag_filter, focus.tag_id),
        ):
            if item_id is not None:
                combo.blockSignals(True)
                combo.select(item_id)
                combo.blockSignals(False)

    def _filter_combos(self) -> tuple[QComboBox, ...]:
        return (
            self.account_filter,
            self.category_filter,
            self.payee_filter,
            self.tag_filter,
            self.type_filter,
        )

    def _reset_filters(self) -> None:
        inputs = (*self._filter_combos(), self.search_input)
        for widget in inputs:  # one reload at the end instead of one per filter
            widget.blockSignals(True)
        for combo in self._filter_combos():
            combo.setCurrentIndex(0)
        self.search_input.clear()
        for widget in inputs:
            widget.blockSignals(False)

    def export_shown(self) -> None:
        """Exports what the table shows: the period with its filters."""
        export_transactions(
            self.window(),
            self._services,
            self._services.transactions.list_transactions(self.current_filter()),
            export_filename(self.period_selector.period()),
        )

    def _has_filters(self) -> bool:
        has_choice = any(combo.currentIndex() > 0 for combo in self._filter_combos())
        return has_choice or bool(self.search_input.text())

    def current_filter(self) -> TransactionFilter:
        period = self.period_selector.period()
        transaction_type, is_transfer, refund_linked = TYPE_FILTERS[self.type_filter.currentText()]
        return TransactionFilter(
            start=period.start,
            end=period.end,
            account_id=self.account_filter.current_id(),
            category_id=self.category_filter.current_id(),
            payee_id=self.payee_filter.current_id(),
            tag_id=self.tag_filter.current_id(),
            type=transaction_type,
            is_transfer=is_transfer,
            refund_linked=refund_linked,
            text=self.search_input.text().strip() or None,
        )

    def selected_items(self) -> list[TransactionListItem]:
        return [self.model.item(row) for row in self.table.selected_rows()]

    def row_actions(self, row: int) -> list[RowAction]:
        """The menu of a row: edit, change its category and delete."""
        item = self.model.item(row)
        actions = [RowAction("Editar", lambda: self.edit(item), "pencil")]
        if not item.is_transfer:
            actions.append(
                RowAction("Cambiar categoría", lambda: self.change_category([item]), "categories")
            )
        actions.append(
            RowAction("Eliminar", lambda: self.delete([item]), "trash", destructive=True)
        )
        return actions

    def edit(self, item: TransactionListItem) -> None:
        TransactionDialog(
            self._services,
            self._event_bus,
            self._theme_manager,
            item.transaction,
            parent=self.window(),
        ).exec()

    def delete_selected(self) -> None:
        self.delete(self.selected_items())

    def delete(self, items: list[TransactionListItem]) -> None:
        """Deletes ``items`` after the user confirms, saying what goes with them."""
        if not items:
            return
        title = "Eliminar transacción" if len(items) == 1 else "Eliminar transacciones"
        if confirm(self.window(), title, self._delete_warning(items)):
            self._services.transactions.delete_many([item.transaction.id for item in items])
            self._event_bus.transactions_changed.emit()

    def _delete_warning(self, items: list[TransactionListItem]) -> str:
        if len(items) == 1:
            item = items[0]
            text = (
                "Se va a eliminar la transferencia, con el movimiento de las dos cuentas."
                if item.is_transfer
                else f"Se va a eliminar «{item.description}» del {format_date(item.occurred_on)}."
            )
        else:
            text = f"Se van a eliminar {transactions_text(len(items))}."
            if any(item.is_transfer for item in items):
                text += " Las transferencias se eliminan con el movimiento de las dos cuentas."
        refunds = sum(
            len(self._services.transactions.refund_summary(item.transaction.id).refunds)
            for item in items
            if not item.is_transfer
        )
        if refunds == 1 and len(items) == 1:
            text += " Su reembolso queda como un ingreso común."
        elif refunds == 1:
            text += " Un reembolso queda como un ingreso común."
        elif refunds:
            owner = "Sus" if len(items) == 1 else "Los"
            text += f" {owner} {refunds} reembolsos quedan como ingresos comunes."
        return text

    def change_category_of_selected(self) -> None:
        self.change_category(self.selected_items())

    def change_category(self, items: list[TransactionListItem]) -> None:
        """Moves ``items``, all expenses or all incomes, to a category the user picks."""
        kind = common_kind(items)
        if kind is None:
            return
        ChangeCategoryDialog(
            self._services,
            self._event_bus,
            [item.transaction.id for item in items],
            kind,
            parent=self.window(),
        ).exec()

    def _fit_columns(self) -> None:
        header = self.table.horizontalHeader()
        for column, max_width in MAX_COLUMN_WIDTHS.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(column, min(self.table.sizeHintForColumn(column), max_width))

    def _build_table(self) -> SelectableTable:
        table = SelectableTable(self.model, DESCRIPTION, self.row_actions)
        table.row_activated.connect(lambda row: self.edit(self.model.item(row)))
        bind_delete_key(table, self.delete_selected)
        table.selection_changed.connect(self._update_actions)
        return table

    def _update_actions(self) -> None:
        """With two or more rows chosen, the header becomes the selection bar, with what
        they add up to and whether they can change category together."""
        items = self.selected_items()
        several = len(items) > 1
        self.show_selection_bar(several)
        if not several:
            return
        totals = self._services.dashboard.totals_of([item.transaction for item in items])
        self.selection_bar.set_count(len(items), selection_totals_text(totals))
        movable = common_kind(items) is not None
        self.category_button.setEnabled(movable)
        self.category_button.setToolTip(
            "" if movable else "Solo si todas son gastos o todas son ingresos"
        )
