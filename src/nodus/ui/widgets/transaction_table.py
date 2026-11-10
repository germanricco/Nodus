"""The table of movements, shared by the transactions page and the refund picker."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from nodus.ui.formatting import format_date
from nodus.ui.theme.theme import Theme
from nodus.ui.transaction_list import REFUND_MARK, TransactionListItem, upcoming_text
from nodus.ui.widgets.color import color_icon, colors_icon

DATE, DESCRIPTION, PAYEE, CATEGORY, TAGS, ACCOUNT, AMOUNT = range(7)
COLUMN_TITLES = [
    "Fecha", "Descripción", "Beneficiario", "Categoría", "Etiquetas", "Cuenta", "Monto"
]  # fmt: skip


_ModelIndex = QModelIndex | QPersistentModelIndex


class TransactionTableModel(QAbstractTableModel):
    """Exposes list items to a table view, coloring amounts with the current theme. A
    movement still to come off the account is dimmed, all of it."""

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
            last = self.index(len(self._items) - 1, AMOUNT)
            self.dataChanged.emit(self.index(0, DATE), last)

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
        if role == Qt.ItemDataRole.DecorationRole and column == TAGS and item.tags:
            return colors_icon([tag.color for tag in item.tags])
        if role == Qt.ItemDataRole.ForegroundRole and item.upcoming:
            return QColor(self._theme.text_muted)
        if role == Qt.ItemDataRole.ForegroundRole and column == AMOUNT:
            return QColor(self._theme.tone_color(item.tone))
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(item, column)
        if role == Qt.ItemDataRole.TextAlignmentRole and column == AMOUNT:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def _tooltip(self, item: TransactionListItem, column: int) -> str | None:
        """The whole text of a cell, which narrow columns cut with "…"; the description
        of a refund says what it pays back instead."""
        if column == DESCRIPTION and item.refund_text:
            return item.refund_text
        if column in (DATE, AMOUNT) and item.upcoming:
            return upcoming_text(item.occurred_on)
        if column in (DATE, AMOUNT):
            return None
        return self._text(item, column) or None

    @staticmethod
    def _text(item: TransactionListItem, column: int) -> str:
        return [
            format_date(item.occurred_on),
            f"{REFUND_MARK} {item.description}" if item.refund_text else item.description,
            item.payee_name,
            item.category_name,
            ", ".join(tag.name for tag in item.tags),
            item.account_text,
            item.amount_text,
        ][column]
