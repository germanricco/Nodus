"""Transactions section: every movement of a month, with filters."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableView

from nodus.database.repositories.transaction_repository import TransactionFilter
from nodus.models.period import Period
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.export import export_transactions
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder, TransactionListItem
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.selectors import AccountComboBox, CategoryComboBox, PayeeComboBox
from nodus.ui.widgets.table import record_table
from nodus.ui.widgets.transaction_table import DESCRIPTION, TransactionTableModel

# Type filter: label -> (transaction type, is_transfer, refund_linked) criteria.
TYPE_FILTERS = {
    "Todos los tipos": (None, None, None),
    "Gastos": (TransactionType.EXPENSE, False, None),
    "Ingresos": (TransactionType.INCOME, False, None),
    "Transferencias": (None, True, None),
    "Reembolsos": (None, False, True),
}


def export_filename(period: Period) -> str:
    """ "nodus-transacciones-2026-11.csv" for a month, start and end dates otherwise."""
    if period.is_whole_months and period.first_month == period.last_month:
        return f"nodus-transacciones-{period.start:%Y-%m}.csv"
    return f"nodus-transacciones-{period.start:%Y-%m-%d}_{period.end:%Y-%m-%d}.csv"


class TransactionsPage(Page):
    """The movements of a period, newest first, narrowed by account, category, payee, type
    or text.

    Double-clicking a row edits it. A transfer shows as one row for both of its legs.
    """

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
        self.export_button = self.add_header_button("Exportar")
        self.export_button.setToolTip("Guarda en un archivo CSV los movimientos que se ven")
        self.export_button.clicked.connect(self.export_shown)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)

        self.account_filter = AccountComboBox()
        self.category_filter = CategoryComboBox()
        self.payee_filter = PayeeComboBox()
        self.type_filter = QComboBox()
        self.type_filter.addItems(list(TYPE_FILTERS))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar…")
        self.search_input.setToolTip("Busca en la nota y en el nombre del beneficiario")
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
        self.content_layout.addWidget(card, stretch=1)

        self.period_selector.period_changed.connect(self.reload)
        self.account_filter.currentIndexChanged.connect(self.reload)
        self.category_filter.currentIndexChanged.connect(self.reload)
        self.payee_filter.currentIndexChanged.connect(self.reload)
        self.type_filter.currentIndexChanged.connect(self.reload)
        self.search_input.textChanged.connect(self.reload)
        theme_manager.theme_changed.connect(self.model.set_theme)
        for signal in (
            event_bus.transactions_changed,
            event_bus.accounts_changed,
            event_bus.categories_changed,
            event_bus.payees_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        """Reloads the filter choices (keeping the selection) and then the movements."""
        self._load_filter_choices()
        self.reload()

    def _load_filter_choices(self) -> None:
        self.account_filter.set_accounts(
            self._services.accounts.list_accounts(include_archived=True), "Todas las cuentas"
        )
        categories = self._services.categories
        self.category_filter.set_categories(
            [
                ("Gastos", categories.category_tree(TransactionType.EXPENSE)),
                ("Ingresos", categories.category_tree(TransactionType.INCOME)),
            ],
            "Todas las categorías",
        )
        self.payee_filter.set_payees(self._services.payees.list_payees(), "Todos los beneficiarios")

    def reload(self) -> None:
        """Lists the movements matching the current filters."""
        transactions = self._services.transactions.list_transactions(self.current_filter())
        self.model.set_items(self._builder.build(transactions))
        has_rows = self.model.rowCount() > 0
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)
        self._update_actions()
        self.clear_filters_button.setEnabled(self._has_filters())

    def clear_filters(self) -> None:
        """Back to every movement of the period shown; the period itself is kept."""
        self._reset_filters()
        self.reload()

    def focus(
        self, period: Period, category_id: int | None = None, payee_id: int | None = None
    ) -> None:
        """Shows ``period`` with only ``category_id`` or ``payee_id`` filtered, as the
        dashboard, budgets and payees pages ask for.

        Does not reload: the caller shows the page, which refreshes it.
        """
        self._load_filter_choices()
        self._reset_filters()
        self.period_selector.blockSignals(True)
        self.period_selector.set_period(period)
        self.period_selector.blockSignals(False)
        for combo, item_id in ((self.category_filter, category_id), (self.payee_filter, payee_id)):
            if item_id is not None:
                combo.blockSignals(True)
                combo.select(item_id)
                combo.blockSignals(False)

    def _filter_combos(self) -> tuple[QComboBox, ...]:
        return (self.account_filter, self.category_filter, self.payee_filter, self.type_filter)

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

    def _build_table(self) -> QTableView:
        table = record_table(self.model, DESCRIPTION)
        table.doubleClicked.connect(lambda _index: self.edit_selected())
        table.selectionModel().selectionChanged.connect(self._update_actions)
        return table

    def _update_actions(self) -> None:
        has_selection = self.selected_item() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
