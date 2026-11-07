"""A page listing named items (payees, tags) with how many movements each has and their net
total, searchable and sortable, with the actions to create, edit, merge and delete them."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

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

from nodus.models.money import Money
from nodus.models.payee import normalize_name
from nodus.services.sorting import name_sort_key
from nodus.ui.labels import unconverted_note
from nodus.ui.navigation import TransactionFocus
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.table import DELETE_KEY_HINT, bind_delete_key, record_table

# The first three columns of every summary table; subclasses may add more after them.
NAME, COUNT, TOTAL = range(3)

# The value each column sorts by, so numbers sort as numbers and names ignore accents.
SORT_ROLE = Qt.ItemDataRole.UserRole

_ModelIndex = QModelIndex | QPersistentModelIndex
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class Summary(Protocol):
    """What a row needs: its movements counted and added up in pesos."""

    count: int
    net: Money
    unconverted: int


S = TypeVar("S", bound=Summary)


class SummaryTableModel(QAbstractTableModel, Generic[S]):
    """Name, movements and net total of each summary, totals colored with the theme.

    Subclasses give the name and may add columns through ``extra_text``, ``extra_sort``
    and ``decoration``.
    """

    TITLES = ["Nombre", "Movimientos", "Total"]

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self._summaries: list[S] = []
        self._theme = theme

    def name(self, summary: S) -> str:
        raise NotImplementedError

    def extra_text(self, summary: S, column: int) -> str:
        raise NotImplementedError

    def extra_sort(self, summary: S, column: int) -> object:
        raise NotImplementedError

    def decoration(self, summary: S, column: int) -> object:
        return None

    def set_summaries(self, summaries: list[S]) -> None:
        self.beginResetModel()
        self._summaries = summaries
        self.endResetModel()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        if self._summaries:
            last = len(self._summaries) - 1
            self.dataChanged.emit(self.index(0, TOTAL), self.index(last, TOTAL))

    def summary(self, row: int) -> S:
        return self._summaries[row]

    def rowCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._summaries)

    def columnCount(self, parent: _ModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.TITLES)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = 0) -> object:  # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.TITLES[section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section in (COUNT, TOTAL):
            return _RIGHT
        return None

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        summary = self._summaries[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(summary, column)
        if role == SORT_ROLE:
            return self._sort_value(summary, column)
        if role == Qt.ItemDataRole.DecorationRole:
            return self.decoration(summary, column)
        if role == Qt.ItemDataRole.ForegroundRole and column == TOTAL:
            return QColor(self._theme.amount_color(summary.net))
        if role == Qt.ItemDataRole.ToolTipRole and column == TOTAL and summary.unconverted:
            return unconverted_note(summary.unconverted)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in (COUNT, TOTAL):
            return _RIGHT
        return None

    def _text(self, summary: S, column: int) -> str:
        if column == NAME:
            return self.name(summary)
        if column == COUNT:
            return str(summary.count)
        if column == TOTAL:
            return summary.net.format() if summary.count else "—"
        return self.extra_text(summary, column)

    def _sort_value(self, summary: S, column: int) -> object:
        if column == NAME:
            return name_sort_key(self.name(summary))
        if column == COUNT:
            return summary.count
        if column == TOTAL:
            return summary.net.cents
        return self.extra_sort(summary, column)


class SummaryPage(Page, Generic[S]):
    """Every item with its movements, sortable by any column, with a search that ignores
    case and accents. Double-click or "Ver movimientos" opens the item's transactions.

    Subclasses load the summaries and carry out the actions.
    """

    transactions_requested = Signal(object)  # TransactionFocus

    def __init__(
        self,
        title: str,
        noun: str,
        texts: tuple[str, str],
        model: SummaryTableModel[S],
        theme_manager: ThemeManager,
    ) -> None:
        """``noun`` names one item ("beneficiario"); ``texts`` are what the empty table
        says when there are no items at all and when none matches the search."""
        super().__init__(title)
        self._no_items_text, self._no_matches_text = texts
        self._summaries: list[S] = []

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"Buscar {noun}…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(200)
        self.add_header_widget(self.search_input)
        self.transactions_button = self.add_header_button("Ver movimientos")
        self.edit_button = self.add_header_button("Editar")
        self.merge_button = self.add_header_button("Unir con…")
        self.delete_button = self.add_header_button("Eliminar")
        self.delete_button.setToolTip(DELETE_KEY_HINT)
        self.create_button = self.add_header_button(f"Crear {noun}", primary=True)

        self.model = model
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
        self.create_button.clicked.connect(self.create_item)
        self.transactions_button.clicked.connect(self.show_selected_transactions)
        self.edit_button.clicked.connect(lambda: self._with_selected(self.edit_item))
        self.merge_button.clicked.connect(lambda: self._with_selected(self.merge_item))
        self.delete_button.clicked.connect(lambda: self._with_selected(self.delete_item))
        theme_manager.theme_changed.connect(self.model.set_theme)

    # To implement

    def load_summaries(self) -> list[S]:
        raise NotImplementedError

    def focus_of(self, summary: S) -> TransactionFocus:
        """The movements of ``summary``, which has at least one."""
        raise NotImplementedError

    def create_item(self) -> None:
        raise NotImplementedError

    def edit_item(self, summary: S) -> None:
        raise NotImplementedError

    def merge_item(self, summary: S) -> None:
        raise NotImplementedError

    def delete_item(self, summary: S) -> None:
        raise NotImplementedError

    # Shared

    def refresh(self) -> None:
        self._summaries = self.load_summaries()
        self._show_matches()

    def selected_summary(self) -> S | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.model.summary(self.proxy.mapToSource(rows[0]).row())

    def show_selected_transactions(self) -> None:
        summary = self.selected_summary()
        if summary is not None and summary.count:
            self.transactions_requested.emit(self.focus_of(summary))

    def _with_selected(self, action) -> None:
        summary = self.selected_summary()
        if summary is not None:
            action(summary)

    def _show_matches(self) -> None:
        wanted = normalize_name(self.search_input.text())
        self.model.set_summaries(
            [s for s in self._summaries if wanted in normalize_name(self.model.name(s))]
        )
        has_rows = self.model.rowCount() > 0
        self.table.setVisible(has_rows)
        self.empty_label.setText(self._no_matches_text if self._summaries else self._no_items_text)
        self.empty_label.setVisible(not has_rows)
        self._update_actions()

    def _build_table(self) -> QTableView:
        table = record_table(self.proxy, NAME)
        table.setObjectName("SortableTable")
        table.setSortingEnabled(True)
        table.sortByColumn(COUNT, Qt.SortOrder.DescendingOrder)
        table.doubleClicked.connect(lambda _index: self.show_selected_transactions())
        bind_delete_key(table, lambda: self._with_selected(self.delete_item))
        table.selectionModel().selectionChanged.connect(self._update_actions)
        return table

    def _update_actions(self) -> None:
        summary = self.selected_summary()
        self.transactions_button.setEnabled(bool(summary and summary.count))
        self.edit_button.setEnabled(summary is not None)
        self.merge_button.setEnabled(summary is not None and len(self._summaries) > 1)
        self.delete_button.setEnabled(summary is not None)
