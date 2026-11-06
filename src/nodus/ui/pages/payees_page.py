"""Payees section: who the user pays and who pays them, with what each adds up to."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QLineEdit, QTableView

from nodus.models.payee import normalize_name
from nodus.models.period import Month, Period
from nodus.services.container import Services
from nodus.services.payee_service import PayeeSummary
from nodus.services.sorting import name_sort_key
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.payee_dialogs import MergePayeeDialog, PayeeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import movements_text, unconverted_note
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.color import color_icon
from nodus.ui.widgets.table import record_table

NAME, COUNT, TOTAL, CATEGORY = range(4)
COLUMN_TITLES = ["Nombre", "Movimientos", "Total", "Categoría habitual"]
NO_PAYEES_TEXT = "Aún no hay beneficiarios: se crean al escribir uno nuevo al cargar un movimiento."
NO_MATCHES_TEXT = "Ningún beneficiario coincide con la búsqueda"

# The value each column sorts by, so numbers sort as numbers and names ignore accents.
SORT_ROLE = Qt.ItemDataRole.UserRole

_ModelIndex = QModelIndex | QPersistentModelIndex
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class PayeeTableModel(QAbstractTableModel):
    """Exposes payee summaries to a table view, coloring totals with the current theme."""

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self._summaries: list[PayeeSummary] = []
        self._theme = theme

    def set_summaries(self, summaries: list[PayeeSummary]) -> None:
        self.beginResetModel()
        self._summaries = summaries
        self.endResetModel()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self._summaries:
            last = len(self._summaries) - 1
            self.dataChanged.emit(self.index(0, TOTAL), self.index(last, TOTAL))

    def summary(self, row: int) -> PayeeSummary:
        return self._summaries[row]

    def rowCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._summaries)

    def columnCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(COLUMN_TITLES)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> object:  # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMN_TITLES[section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section in (COUNT, TOTAL):
            return _RIGHT
        return None

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        summary = self._summaries[index.row()]
        column = index.column()
        category = summary.top_category
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(summary, column)
        if role == SORT_ROLE:
            return self._sort_value(summary, column)
        if role == Qt.ItemDataRole.DecorationRole and column == CATEGORY and category:
            return color_icon(category.color)
        if role == Qt.ItemDataRole.ForegroundRole and column == TOTAL:
            return QColor(self._theme.tone_color(_tone(summary)))
        if role == Qt.ItemDataRole.ToolTipRole and column == TOTAL and summary.unconverted:
            return unconverted_note(summary.unconverted)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in (COUNT, TOTAL):
            return _RIGHT
        return None

    @staticmethod
    def _text(summary: PayeeSummary, column: int) -> str:
        category = summary.top_category
        return [
            summary.payee.name,
            str(summary.count),
            summary.net.format() if summary.count else "—",
            category.name if category else "—",
        ][column]

    @staticmethod
    def _sort_value(summary: PayeeSummary, column: int) -> object:
        category = summary.top_category
        return [
            name_sort_key(summary.payee.name),
            summary.count,
            summary.net.cents,
            name_sort_key(category.name) if category else "",
        ][column]


def _tone(summary: PayeeSummary) -> str:
    if summary.net.is_negative:
        return "negative"
    return "neutral" if summary.net.is_zero else "positive"


class PayeesPage(Page):
    """Every payee with its number of movements, net total and usual category.

    The table sorts by any column and the search ignores case and accents. Double-click
    or "Ver movimientos" opens the payee's transactions over its whole history.
    """

    transactions_requested = Signal(object, int)  # Period, payee id

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Beneficiarios")
        self._services = services
        self._event_bus = event_bus
        self._summaries: list[PayeeSummary] = []

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar beneficiario…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(200)
        self.add_header_widget(self.search_input)
        self.transactions_button = self.add_header_button("Ver movimientos")
        self.edit_button = self.add_header_button("Editar")
        self.merge_button = self.add_header_button("Unir con…")
        self.delete_button = self.add_header_button("Eliminar")
        self.create_button = self.add_header_button("Crear beneficiario", primary=True)

        self.model = PayeeTableModel(theme_manager.theme)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.table = self._build_table()
        self.empty_label = QLabel()
        self.empty_label.setObjectName("EmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        card = Card()
        card.body.setContentsMargins(8, 8, 8, 8)
        card.body.addWidget(self.table)
        card.body.addWidget(self.empty_label, stretch=1)
        self.content_layout.addWidget(card, stretch=1)

        self.search_input.textChanged.connect(self._show_matches)
        self.create_button.clicked.connect(self.create_payee)
        self.transactions_button.clicked.connect(self.show_selected_transactions)
        self.edit_button.clicked.connect(self.edit_selected)
        self.merge_button.clicked.connect(self.merge_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        theme_manager.theme_changed.connect(self.model.set_theme)
        for signal in (
            event_bus.payees_changed,
            event_bus.transactions_changed,
            event_bus.categories_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.connect(self.refresh)

    def refresh(self) -> None:
        self._summaries = self._services.payees.summaries()
        self._show_matches()

    def _show_matches(self) -> None:
        wanted = normalize_name(self.search_input.text())
        self.model.set_summaries([s for s in self._summaries if wanted in s.payee.normalized_name])
        has_rows = self.model.rowCount() > 0
        self.table.setVisible(has_rows)
        self.empty_label.setText(NO_MATCHES_TEXT if self._summaries else NO_PAYEES_TEXT)
        self.empty_label.setVisible(not has_rows)
        self._update_actions()

    def selected_summary(self) -> PayeeSummary | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.model.summary(self.proxy.mapToSource(rows[0]).row())

    # Actions

    def create_payee(self) -> None:
        PayeeDialog(self._services, self._event_bus, parent=self.window()).exec()

    def show_selected_transactions(self) -> None:
        summary = self.selected_summary()
        if summary is None or summary.first_on is None:
            return
        last = max(summary.last_on, date.today())
        period = Period.of_months(Month.of(summary.first_on), Month.of(last))
        self.transactions_requested.emit(period, summary.payee.id)

    def edit_selected(self) -> None:
        summary = self.selected_summary()
        if summary:
            PayeeDialog(self._services, self._event_bus, summary.payee, parent=self.window()).exec()

    def merge_selected(self) -> None:
        summary = self.selected_summary()
        if summary:
            MergePayeeDialog(
                self._services, self._event_bus, summary.payee, parent=self.window()
            ).exec()

    def delete_selected(self) -> None:
        summary = self.selected_summary()
        if summary is None:
            return
        text = f"Se va a eliminar «{summary.payee.name}»."
        if summary.count:
            left = "queda" if summary.count == 1 else "quedan"
            text += f" {movements_text(summary.count)} {left} sin beneficiario."
        if confirm(self.window(), "Eliminar beneficiario", text):
            self._services.payees.delete(summary.payee.id)
            self._event_bus.payees_changed.emit()
            self._event_bus.transactions_changed.emit()

    # Building

    def _build_table(self) -> QTableView:
        table = record_table(self.proxy, NAME)
        table.setSortingEnabled(True)
        table.sortByColumn(COUNT, Qt.SortOrder.DescendingOrder)
        table.doubleClicked.connect(lambda _index: self.show_selected_transactions())
        table.selectionModel().selectionChanged.connect(self._update_actions)
        return table

    def _update_actions(self) -> None:
        summary = self.selected_summary()
        self.transactions_button.setEnabled(bool(summary and summary.count))
        self.edit_button.setEnabled(summary is not None)
        self.merge_button.setEnabled(summary is not None and len(self._summaries) > 1)
        self.delete_button.setEnabled(summary is not None)
