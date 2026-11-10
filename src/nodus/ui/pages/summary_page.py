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
from PySide6.QtWidgets import QLineEdit

from nodus.models.money import Money
from nodus.models.payee import normalize_name
from nodus.services.sorting import name_sort_key
from nodus.ui.labels import unconverted_note
from nodus.ui.navigation import TransactionFocus
from nodus.ui.pages.page import Page
from nodus.ui.theme.design import Layout, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.row_actions import RowAction
from nodus.ui.widgets.selectable_table import SelectableTable
from nodus.ui.widgets.selection_bar import SelectionBar
from nodus.ui.widgets.table import DELETE_KEY_HINT, bind_delete_key

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
    case and accents. A double click opens the item's page; its «⋯» or a right
    click offers every action, and several rows can be chosen to merge or delete them.

    Subclasses load the summaries and carry out the actions.
    """

    transactions_requested = Signal(object)  # TransactionFocus
    detail_requested = Signal(int)  # item id

    def __init__(
        self,
        title: str,
        noun: str,
        texts: tuple[str, str],
        model: SummaryTableModel[S],
        theme_manager: ThemeManager,
        chosen_word: str = "seleccionadas",
    ) -> None:
        """``noun`` names one item ("beneficiario"); ``texts`` are what the empty table
        says when there are no items at all and when none matches the search;
        ``chosen_word`` agrees with the items in the selection bar ("seleccionados")."""
        super().__init__(title)
        self._no_items_text, self._no_matches_text = texts
        self._noun = noun
        self._summaries: list[S] = []

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"Buscar {noun}…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(Layout.SEARCH_WIDTH)
        self.add_header_widget(self.search_input)
        self.create_button = self.add_header_button(f"Agregar {noun}", primary=True)
        self.selection_bar = SelectionBar(chosen_word)
        self.merge_button = self.selection_bar.add_action("Unir…", self.merge_selected)
        self.merge_button.setToolTip("Deja uno solo y le pasa los movimientos de los demás")
        self.delete_button = self.selection_bar.add_action(
            "Eliminar", self.delete_selected, destructive=True
        )
        self.delete_button.setToolTip(DELETE_KEY_HINT)
        self.selection_bar.cleared.connect(lambda: self.table.clearSelection())
        self.set_selection_bar(self.selection_bar)

        self.model = model
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.table = self._build_table()
        self.empty_state = EmptyState()
        card = Card()
        card.body.setContentsMargins(Space.S, Space.S, Space.S, Space.S)
        card.body.addWidget(self.table)
        card.body.addWidget(self.empty_state, stretch=1)
        self.content_layout.addWidget(card, stretch=1)

        self.search_input.textChanged.connect(self._show_matches)
        self.create_button.clicked.connect(self.create_item)
        theme_manager.theme_changed.connect(self.model.set_theme)

    # To implement

    def load_summaries(self) -> list[S]:
        raise NotImplementedError

    def item_id(self, summary: S) -> int:
        raise NotImplementedError

    def focus_of(self, summary: S) -> TransactionFocus:
        """The movements of ``summary``, which has at least one."""
        raise NotImplementedError

    def create_item(self) -> None:
        raise NotImplementedError

    def edit_item(self, summary: S) -> None:
        raise NotImplementedError

    def merge_items(self, summaries: list[S]) -> None:
        """One item joins another; several join the one the user keeps."""
        raise NotImplementedError

    def delete_items(self, summaries: list[S]) -> None:
        """Deletes ``summaries`` after the user confirms."""
        raise NotImplementedError

    # Shared

    def refresh(self) -> None:
        self._summaries = self.load_summaries()
        self._show_matches()

    def summary_at(self, row: int) -> S:
        """The item of a table row, which may be sorted differently from the model."""
        return self.model.summary(self.proxy.mapToSource(self.proxy.index(row, 0)).row())

    def selected_summaries(self) -> list[S]:
        return [self.summary_at(row) for row in self.table.selected_rows()]

    def row_actions(self, row: int) -> list[RowAction]:
        """The menu of a row: its page, its movements, edit, merge and delete."""
        summary = self.summary_at(row)
        return [
            RowAction("Abrir", lambda: self.open_detail(summary), default=True),
            RowAction(
                "Ver movimientos",
                lambda: self.show_transactions(summary),
                "list",
                enabled=summary.count > 0,
            ),
            RowAction("Editar", lambda: self.edit_item(summary), "pencil"),
            RowAction(
                "Unir con…",
                lambda: self.merge_items([summary]),
                "merge",
                enabled=len(self._summaries) > 1,
            ),
            RowAction("Eliminar", lambda: self.delete_items([summary]), "trash", destructive=True),
        ]

    def open_detail(self, summary: S) -> None:
        self.detail_requested.emit(self.item_id(summary))

    def show_transactions(self, summary: S) -> None:
        if summary.count:
            self.transactions_requested.emit(self.focus_of(summary))

    def merge_selected(self) -> None:
        summaries = self.selected_summaries()
        if len(summaries) > 1:
            self.merge_items(summaries)

    def delete_selected(self) -> None:
        summaries = self.selected_summaries()
        if summaries:
            self.delete_items(summaries)

    def _show_matches(self) -> None:
        wanted = normalize_name(self.search_input.text())
        self.model.set_summaries(
            [s for s in self._summaries if wanted in normalize_name(self.model.name(s))]
        )
        has_rows = self.model.rowCount() > 0
        self.table.setVisible(has_rows)
        if self._summaries:
            self.empty_state.set_message(
                self._no_matches_text, "Borrar búsqueda", self.search_input.clear
            )
        else:
            self.empty_state.set_message(
                self._no_items_text, f"Agregar {self._noun}", self.create_item
            )
        self.empty_state.setVisible(not has_rows)
        self._update_actions()

    def _build_table(self) -> SelectableTable:
        table = SelectableTable(self.proxy, NAME, self.row_actions)
        table.setObjectName("SortableTable")
        table.setSortingEnabled(True)
        table.sortByColumn(COUNT, Qt.SortOrder.DescendingOrder)
        bind_delete_key(table, self.delete_selected)
        table.selection_changed.connect(self._update_actions)
        return table

    def _update_actions(self) -> None:
        """With two or more rows chosen, the header becomes the selection bar."""
        count = len(self.table.selected_rows())
        self.show_selection_bar(count > 1)
        if count > 1:
            self.selection_bar.set_count(count)
