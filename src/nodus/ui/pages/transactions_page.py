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
    QTableView,
)

from nodus.models.period import Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.container import Services
from nodus.services.dashboard_service import FilteredTotals
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.export import export_transactions
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.labels import movements_text, unconverted_note
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder, TransactionListItem
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.selectors import (
    AccountComboBox,
    CategoryComboBox,
    PayeeComboBox,
    TagComboBox,
)
from nodus.ui.widgets.style import set_style_property
from nodus.ui.widgets.table import DELETE_KEY_HINT, bind_delete_key, record_table
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
MAX_COLUMN_WIDTHS = {PAYEE: 120, CATEGORY: 150, TAGS: 130, ACCOUNT: 120}

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
    if count and (totals.income.cents or totals.expenses.cents):
        parts += [
            f"Ingresos {totals.income.format()}",
            f"Gastos {totals.expenses.format()}",
            f"Neto {totals.net.format()}",
        ]
    if totals.unconverted:
        parts.append(unconverted_note(totals.unconverted))
    return " · ".join(parts)


def export_filename(period: Period) -> str:
    """ "nodus-transacciones-2026-11.csv" for a month, start and end dates otherwise."""
    if period.is_whole_months and period.first_month == period.last_month:
        return f"nodus-transacciones-{period.start:%Y-%m}.csv"
    return f"nodus-transacciones-{period.start:%Y-%m-%d}_{period.end:%Y-%m-%d}.csv"


class TransactionsPage(Page):
    """The movements of a period, newest first, narrowed by account, category, payee, tag,
    type or text, with what they add up to at the foot.

    Double-clicking a row edits it. A transfer shows as one row for both of its legs. Each
    list filter ends with «Editar», which asks for the page that manages that list.
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
        self.edit_button = self.add_header_button("Editar")
        self.delete_button = self.add_header_button("Eliminar")
        self.delete_button.setToolTip(DELETE_KEY_HINT)
        self.export_button = self.add_header_button("Exportar")
        self.export_button.setToolTip("Guarda en un archivo CSV los movimientos que se ven")
        self.export_button.clicked.connect(self.export_shown)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)

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
        """Shows the period of ``focus`` with only its category, payee or tag filtered, as
        other pages ask for.

        Does not reload: the caller shows the page, which refreshes it.
        """
        self._load_filter_choices()
        self._reset_filters()
        self.period_selector.blockSignals(True)
        self.period_selector.set_period(focus.period)
        self.period_selector.blockSignals(False)
        for combo, item_id in (
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

    def selected_item(self) -> TransactionListItem | None:
        rows = self.table.selectionModel().selectedRows()
        return self.model.item(rows[0].row()) if rows else None

    def edit_selected(self) -> None:
        item = self.selected_item()
        if item:
            TransactionDialog(
                self._services,
                self._event_bus,
                self._theme_manager,
                item.transaction,
                parent=self.window(),
            ).exec()

    def delete_selected(self) -> None:
        item = self.selected_item()
        if item is None:
            return
        text = (
            "Se va a eliminar la transferencia, con el movimiento de las dos cuentas."
            if item.is_transfer
            else f"Se va a eliminar «{item.description}» del {format_date(item.occurred_on)}."
        )
        refunds = len(self._services.transactions.refund_summary(item.transaction.id).refunds)
        if refunds and not item.is_transfer:
            text += (
                " Su reembolso queda como un ingreso común."
                if refunds == 1
                else f" Sus {refunds} reembolsos quedan como ingresos comunes."
            )
        if confirm(self.window(), "Eliminar transacción", text):
            self._services.transactions.delete(item.transaction.id)
            self._event_bus.transactions_changed.emit()

    def _fit_columns(self) -> None:
        header = self.table.horizontalHeader()
        for column, max_width in MAX_COLUMN_WIDTHS.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(column, min(self.table.sizeHintForColumn(column), max_width))

    def _build_table(self) -> QTableView:
        table = record_table(self.model, DESCRIPTION)
        table.doubleClicked.connect(lambda _index: self.edit_selected())
        bind_delete_key(table, self.delete_selected)
        table.selectionModel().selectionChanged.connect(self._update_actions)
        return table

    def _update_actions(self) -> None:
        has_selection = self.selected_item() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
