"""Transactions section: every movement of a month, with filters."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
)

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
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.transaction_list import TransactionListBuilder, TransactionListItem
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.color import color_icon
from nodus.ui.widgets.period_selector import PeriodSelector
from nodus.ui.widgets.selectors import AccountComboBox, CategoryComboBox

# Type filter: label -> (transaction type, is_transfer) criteria.
TYPE_FILTERS = {
    "Todos los tipos": (None, None),
    "Gastos": (TransactionType.EXPENSE, False),
    "Ingresos": (TransactionType.INCOME, False),
    "Transferencias": (None, True),
}

DATE, DESCRIPTION, CATEGORY, ACCOUNT, AMOUNT = range(5)
COLUMN_TITLES = ["Fecha", "Descripción", "Categoría", "Cuenta", "Monto"]


def export_filename(period: Period) -> str:
    """ "nodus-transacciones-2026-11.csv" for a month, start and end dates otherwise."""
    if period.is_whole_months and period.first_month == period.last_month:
        return f"nodus-transacciones-{period.start:%Y-%m}.csv"
    return f"nodus-transacciones-{period.start:%Y-%m-%d}_{period.end:%Y-%m-%d}.csv"


_ModelIndex = QModelIndex | QPersistentModelIndex


class TransactionTableModel(QAbstractTableModel):
    """Exposes list items to a table view, coloring amounts with the current theme."""

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self._items: list[TransactionListItem] = []
        self._theme = theme

    def set_items(self, items: list[TransactionListItem]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self._items:
            self.dataChanged.emit(self.index(0, AMOUNT), self.index(len(self._items) - 1, AMOUNT))

    def item(self, row: int) -> TransactionListItem:
        return self._items[row]

    def rowCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(COLUMN_TITLES)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> object:  # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMN_TITLES[section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section == AMOUNT:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        item = self._items[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(item, column)
        if role == Qt.ItemDataRole.DecorationRole and column == CATEGORY and item.category_color:
            return color_icon(item.category_color)
        if role == Qt.ItemDataRole.ForegroundRole and column == AMOUNT:
            return self._amount_color(item.tone)
        if role == Qt.ItemDataRole.TextAlignmentRole and column == AMOUNT:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    @staticmethod
    def _text(item: TransactionListItem, column: int) -> str:
        return [
            format_date(item.occurred_on),
            item.description,
            item.category_name,
            item.account_text,
            item.amount_text,
        ][column]

    def _amount_color(self, tone: str) -> QColor:
        colors = {"positive": self._theme.income, "negative": self._theme.expense}
        return QColor(colors.get(tone, self._theme.text))


class TransactionsPage(Page):
    """The movements of one month, newest first, narrowed by account, category, type or note.

    Double-clicking a row edits it. A transfer shows as one row for both of its legs.
    """

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Transacciones")
        self._services = services
        self._event_bus = event_bus
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
        self.type_filter = QComboBox()
        self.type_filter.addItems(list(TYPE_FILTERS))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en la nota…")
        self.search_input.setMinimumWidth(140)
        self.search_input.setClearButtonEnabled(True)
        self.clear_filters_button = QPushButton("Limpiar filtros")
        self.clear_filters_button.setObjectName("SecondaryButton")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        for widget in (self.account_filter, self.category_filter, self.type_filter):
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
        self.type_filter.currentIndexChanged.connect(self.reload)
        self.search_input.textChanged.connect(self.reload)
        theme_manager.theme_changed.connect(self.model.set_theme)
        for signal in (
            event_bus.transactions_changed,
            event_bus.accounts_changed,
            event_bus.categories_changed,
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

    def focus(self, period: Period, category_id: int | None = None) -> None:
        """Shows ``period`` with only ``category_id`` filtered, as the dashboard asks for.

        Does not reload: the caller shows the page, which refreshes it.
        """
        self._load_filter_choices()
        self._reset_filters()
        self.period_selector.blockSignals(True)
        self.period_selector.set_period(period)
        self.period_selector.blockSignals(False)
        if category_id is not None:
            self.category_filter.blockSignals(True)
            self.category_filter.select(category_id)
            self.category_filter.blockSignals(False)

    def _reset_filters(self) -> None:
        inputs = (self.account_filter, self.category_filter, self.type_filter, self.search_input)
        for widget in inputs:  # one reload at the end instead of one per filter
            widget.blockSignals(True)
        for combo in inputs[:3]:
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
        combos = (self.account_filter, self.category_filter, self.type_filter)
        return any(combo.currentIndex() > 0 for combo in combos) or bool(self.search_input.text())

    def current_filter(self) -> TransactionFilter:
        period = self.period_selector.period()
        transaction_type, is_transfer = TYPE_FILTERS[self.type_filter.currentText()]
        return TransactionFilter(
            start=period.start,
            end=period.end,
            account_id=self.account_filter.current_id(),
            category_id=self.category_filter.current_id(),
            type=transaction_type,
            is_transfer=is_transfer,
            text=self.search_input.text().strip() or None,
        )

    def selected_item(self) -> TransactionListItem | None:
        rows = self.table.selectionModel().selectedRows()
        return self.model.item(rows[0].row()) if rows else None

    def edit_selected(self) -> None:
        item = self.selected_item()
        if item:
            TransactionDialog(
                self._services, self._event_bus, item.transaction, parent=self.window()
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
        if confirm(self.window(), "Eliminar transacción", text):
            self._services.transactions.delete(item.transaction.id)
            self._event_bus.transactions_changed.emit()

    def _build_table(self) -> QTableView:
        table = QTableView()
        table.setModel(self.model)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(40)
        header = table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for column in range(len(COLUMN_TITLES)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(DESCRIPTION, QHeaderView.ResizeMode.Stretch)
        table.doubleClicked.connect(lambda _index: self.edit_selected())
        table.selectionModel().selectionChanged.connect(self._update_actions)
        return table

    def _update_actions(self) -> None:
        has_selection = self.selected_item() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
