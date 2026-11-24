"""The table of movements, shared by the transactions page, the detail pages and the
refund picker.

Each row reads in the order a movement is thought of: what it was, of what kind, and how
much (plan 029a, 5.5). Four fixed columns (date, movement, category and amount) hold two
lines each, so nothing gets cut and dates, categories and amounts line up on every row;
the initial between the date and the movement is found without reading.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QHelpEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOption,
    QStyleOptionViewItem,
    QTableView,
    QToolTip,
    QWidget,
)

from nodus.i18n import N_, _
from nodus.models.period import format_day_month
from nodus.services.sorting import name_sort_key
from nodus.ui.text.formatting import signed
from nodus.ui.theme.design import ControlSize, IconSize, Layout, RowRole, Space, TextRole, role_font
from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import active_theme
from nodus.ui.transaction_rows import TransactionListItem, upcoming_text
from nodus.ui.widgets.initial_badge import badge_pixmap, icon_badge_pixmap, initial_of
from nodus.ui.widgets.style import make_hoverable
from nodus.ui.widgets.tables.row_actions import RowAction, install_row_actions
from nodus.ui.widgets.tables.selectable_table import RowControlsDelegate, SelectableTable
from nodus.ui.widgets.tables.table import draw_cell_background, drop_columns_to_fit

DATE, BADGE, MOVEMENT, CATEGORY, AMOUNT = range(5)
COLUMN_TITLES = [N_("Fecha"), "", N_("Movimiento"), N_("Categoría"), N_("Monto")]

TRANSFER_MARK = "⇄"
REFUND_MARK = "↺"
# The same signs drawn as icons, since the font has no glyph for them.
TRANSFER_ICON = "transfer"
REFUND_ICON = "refund"

# What a cell shows under its first line, which is its DisplayRole.
SECOND_LINE_ROLE = Qt.ItemDataRole.UserRole + 1
# A category's color for its dot, or the sign a transfer shows in its place.
MARKER_ROLE = Qt.ItemDataRole.UserRole + 2
# What the movement's first line is: a ``Line``.
LINE_ROLE = Qt.ItemDataRole.UserRole + 3

PAYEE_ICON = "payee"  # as Beneficiarios in the sidebar
NO_DESCRIPTION = N_("Sin descripción")

_ModelIndex = QModelIndex | QPersistentModelIndex
_CENTER = Qt.AlignmentFlag.AlignCenter
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


class Line(Enum):
    """What a movement's first line holds, so it reads apart: a payee carries its
    icon, a note goes plain, and a row with neither says so in gray."""

    PAYEE = "payee"
    NOTE = "note"
    BLANK = "blank"


class Omit(Enum):
    """What a detail page's list leaves out because the whole page is about it."""

    PAYEE = "payee"
    ACCOUNT = "account"


class TransactionTableModel(QAbstractTableModel):
    """Exposes list items to a table view, coloring amounts with the current theme. A
    movement still to come off the account is dimmed, all of it.

    It sorts itself when a column's title is clicked, newest first by default, and keeps
    that order when the list reloads.
    """

    def __init__(
        self, theme: Theme, omit: Omit | None = None, date_under_amount: bool = False
    ) -> None:
        """``date_under_amount`` is for a list with no room for the date's column, such as
        ``CompactMovementRow``'s: the date goes under the amount instead."""
        super().__init__()
        self._loaded: list[TransactionListItem] = []
        self._items: list[TransactionListItem] = []
        self._theme = theme
        self._omit = omit
        self._date_under_amount = date_under_amount
        self._sort_column = DATE
        self._sort_order = Qt.SortOrder.DescendingOrder

    def set_items(self, items: list[TransactionListItem]) -> None:
        """``items`` newest first, as the services list them; shown in the current order."""
        self.beginResetModel()
        self._loaded = items
        self._items = self._sorted()
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
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return _(COLUMN_TITLES[section]) if COLUMN_TITLES[section] else ""
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return {DATE: _CENTER, AMOUNT: _RIGHT}.get(section, _LEFT)
        return None

    @property
    def sort_column(self) -> int:
        return self._sort_column

    @property
    def sort_order(self) -> Qt.SortOrder:
        return self._sort_order

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if column == BADGE:  # the initials have no order of their own
            return
        self.layoutAboutToBeChanged.emit()
        self._sort_column, self._sort_order = column, order
        self._items = self._sorted()
        self.layoutChanged.emit()

    def _sorted(self) -> list[TransactionListItem]:
        """The loaded items in the chosen order. Ties keep the newest first, as loaded."""
        if self._sort_column == DATE:
            newest_first = list(self._loaded)
            ascending = self._sort_order == Qt.SortOrder.AscendingOrder
            return newest_first[::-1] if ascending else newest_first
        keys: dict[int, Callable[[TransactionListItem], object]] = {
            MOVEMENT: self._movement_key,
            CATEGORY: lambda item: name_sort_key(item.category_name),
            AMOUNT: _amount_key,
        }
        descending = self._sort_order == Qt.SortOrder.DescendingOrder
        return sorted(self._loaded, key=keys[self._sort_column], reverse=descending)

    def data(self, index: _ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        item = self._items[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._first_line(item, column)
        if role == SECOND_LINE_ROLE:
            return self._second_line(item, column)
        if role == Qt.ItemDataRole.DecorationRole and column == BADGE:
            return self._badge(item)
        if role == LINE_ROLE and column == MOVEMENT:
            return self.movement_lines(item)[2]
        if role == MARKER_ROLE and column == CATEGORY:
            return TRANSFER_MARK if item.is_transfer else item.category_color
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._color(item, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(item, column)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return " · ".join(self._full_lines(item, column))
        return None

    def movement_lines(self, item: TransactionListItem) -> tuple[str, str, Line]:
        """Who was paid (or who paid) above, and the note with the account below. With
        no payee, or on the payee's own page, the note goes up and the account stays
        below; with neither, «Sin descripción». The category is not repeated here: it has
        its column. A transfer shows its accounts as «Banco → Ahorro en dólares»."""
        if item.is_transfer:
            return item.description, item.account_text, Line.NOTE
        account = "" if self._omit is Omit.ACCOUNT else item.account_text
        if item.payee_name and self._omit is not Omit.PAYEE:
            details = " · ".join(part for part in (item.note, account) if part)
            return item.payee_name, details, Line.PAYEE
        if item.note:
            return item.note, account, Line.NOTE
        return _(NO_DESCRIPTION), account, Line.BLANK

    def _movement_key(self, item: TransactionListItem) -> tuple[bool, str]:
        """By name, with the rows that have none at the end."""
        first, _second, line = self.movement_lines(item)
        return line is Line.BLANK, name_sort_key(first)

    def _full_lines(self, item: TransactionListItem, column: int) -> list[str]:
        """A cell's lines as a screen reader or a tooltip says them: a payee, named so."""
        first, second = self._first_line(item, column), self._second_line(item, column)
        if column == MOVEMENT and self.movement_lines(item)[2] is Line.PAYEE:
            first = _("Beneficiario: {name}").format(name=first)
        return [line for line in (first, second) if line]

    def _first_line(self, item: TransactionListItem, column: int) -> str:
        if column == DATE:
            return format_day_month(item.occurred_on)
        if column == BADGE:
            return self._badge_letter(item)
        if column == MOVEMENT:
            return self.movement_lines(item)[0]
        if column == CATEGORY:
            return item.category_name
        if item.is_transfer:
            return item.short_amount_text
        return signed(item.transaction.signed_amount)

    def _second_line(self, item: TransactionListItem, column: int) -> str:
        if column == MOVEMENT:
            return self.movement_lines(item)[1]
        if column == CATEGORY:
            return ", ".join(tag.name for tag in item.tags)
        if column == AMOUNT and self._date_under_amount:
            return format_day_month(item.occurred_on)
        if column == AMOUNT and item.received_text:
            return f"→ {item.received_text}"
        if column == AMOUNT and item.refund_text and not item.is_refund:
            return item.refund_text  # what came back of an expense
        return ""

    def _badge_letter(self, item: TransactionListItem) -> str:
        """The initial of the payee or the note; of the category when there is neither."""
        if item.is_transfer:
            return TRANSFER_MARK
        if item.is_refund:
            return REFUND_MARK
        first, _second, line = self.movement_lines(item)
        return initial_of(item.category_name if line is Line.BLANK else first)

    def _badge(self, item: TransactionListItem) -> QPixmap:
        """The initial in the category's color; a transfer and a refund, their icon."""
        color = item.category_color or self._theme.text_muted
        if item.is_transfer:
            return icon_badge_pixmap(TRANSFER_ICON, color)
        if item.is_refund:
            return icon_badge_pixmap(REFUND_ICON, color)
        return badge_pixmap(self._badge_letter(item), color)

    def _color(self, item: TransactionListItem, column: int) -> QColor | None:
        if item.upcoming:
            return QColor(self._theme.text_muted)
        if column == AMOUNT:
            return QColor(self._theme.tone_color(item.tone))
        if column == CATEGORY and item.is_transfer:
            return QColor(self._theme.text_muted)
        return None

    def _tooltip(self, item: TransactionListItem, column: int) -> str | None:
        """The whole text of a cell, which a narrow window cuts with "…"; a refund says
        what it pays back, and a movement still to come when it comes off."""
        if column in (DATE, AMOUNT) and item.upcoming:
            return upcoming_text(item.occurred_on)
        if column == MOVEMENT and item.refund_text:
            return item.refund_text
        if column in (DATE, BADGE):
            return None
        if column == AMOUNT and self._date_under_amount:
            return item.amount_text if item.received_text else None
        if column == AMOUNT:  # only what comes back of an expense can be cut
            return self._second_line(item, column) or None
        return "\n".join(self._full_lines(item, column)) or None


def _amount_key(item: TransactionListItem) -> int:
    """Expenses below zero and income above; a transfer by what left, as it shows."""
    if item.is_transfer:
        return item.transaction.amount.cents
    return item.transaction.signed_amount.cents


def paint_movement_cell(
    painter: QPainter, option: QStyleOptionViewItem, content: QRect, index: QModelIndex
) -> None:
    """What goes in a cell of a movement's row, within ``content``: the date and the
    initial centered in the row; the other columns in two lines at the same height on
    every column, so the first lines and the second lines each read as one."""
    theme = active_theme()
    area = content.adjusted(Space.S, 0, -Space.S, 0)
    column = index.column()
    first = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
    second = str(index.data(SECOND_LINE_ROLE) or "")
    foreground = index.data(Qt.ItemDataRole.ForegroundRole)
    color = foreground if isinstance(foreground, QColor) else QColor(theme.text)
    muted = QColor(theme.text_muted)
    painter.save()
    if column == BADGE:
        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(pixmap, QPixmap):
            size = pixmap.deviceIndependentSize()
            painter.drawPixmap(
                QPointF(
                    area.center().x() - size.width() / 2 + 1,
                    area.center().y() - size.height() / 2 + 1,
                ),
                pixmap,
            )
    elif column == DATE:
        _draw_text(painter, area, first, role_font(TextRole.BODY), color, _CENTER)
    else:
        strong = column in (MOVEMENT, AMOUNT)
        first_font = role_font(TextRole.STRONG if strong else TextRole.BODY)
        second_font = role_font(TextRole.NOTE)
        first_height = max(ControlSize.FIRST_LINE, QFontMetrics(first_font).height())
        second_height = max(ControlSize.SECOND_LINE, QFontMetrics(second_font).height())
        top = area.top() + (area.height() - first_height - second_height) // 2
        first_line = QRect(area.left(), top, area.width(), first_height)
        second_line = QRect(area.left(), top + first_height, area.width(), second_height)
        align = _RIGHT if column == AMOUNT else _LEFT
        if column == CATEGORY:
            first_line, second_line = _beside_marker(painter, index, first_line, second_line)
        line = index.data(LINE_ROLE)
        if line is Line.PAYEE:
            first_line = _beside_payee_icon(painter, first_line, muted)
        elif line is Line.BLANK:
            first_font, color = role_font(TextRole.BODY), muted
        _draw_text(painter, first_line, first, first_font, color, align)
        _draw_text(painter, second_line, second, second_font, muted, align)
    painter.restore()


def _beside_payee_icon(painter: QPainter, first_line: QRect, color: QColor) -> QRect:
    """Draws the payee's icon at the start of ``first_line``, so a payee reads apart from
    a note, and gives back the room beside it."""
    icon = tinted_pixmap(PAYEE_ICON, color.name(), IconSize.S)
    painter.drawPixmap(
        QPointF(first_line.left(), first_line.center().y() - IconSize.S / 2 + 1), icon
    )
    return first_line.adjusted(IconSize.S + Space.XS, 0, 0, 0)


def _beside_marker(
    painter: QPainter, index: QModelIndex, first_line: QRect, second_line: QRect
) -> tuple[QRect, QRect]:
    """Draws the category's dot (or a transfer's «⇄») in a column of its own and gives
    back the lines beside it, so the tags start under the category's first letter."""
    marker = index.data(MARKER_ROLE)
    dot = ControlSize.DOT_SMALL
    room = dot + Space.S
    if marker == TRANSFER_MARK:
        icon = tinted_pixmap(TRANSFER_ICON, active_theme().text_muted, IconSize.XS)
        painter.drawPixmap(
            QPointF(
                first_line.left() + (dot - IconSize.XS) / 2,
                first_line.center().y() - IconSize.XS / 2 + 1,
            ),
            icon,
        )
    elif marker:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(str(marker)))
        center_y = first_line.center().y() + 1
        painter.drawEllipse(QRectF(first_line.left(), center_y - dot / 2, dot, dot))
    return first_line.adjusted(room, 0, 0, 0), second_line.adjusted(room, 0, 0, 0)


def _draw_text(
    painter: QPainter,
    area: QRect,
    text: str,
    font: QFont,
    color: QColor,
    align: Qt.AlignmentFlag,
) -> None:
    """``text`` in one line within ``area``, ending in "…" when it does not fit."""
    if not text:
        return
    painter.setFont(font)
    painter.setPen(color)
    elided = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, area.width())
    painter.drawText(area, align, elided)


class MovementRowDelegate(RowControlsDelegate):
    """Draws a ``SelectableTable``'s movements in two lines, beside its check boxes and
    «⋯»."""

    def paint_cell(
        self,
        painter: QPainter,
        item: QStyleOptionViewItem,
        content: QRect,
        index: QModelIndex,
    ) -> None:
        draw_cell_background(painter, item, item.widget)
        paint_movement_cell(painter, item, content, index)


class _MovementDelegate(QStyledItemDelegate):
    """Draws the movements of a plain table, such as the refund picker's, in two lines."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        draw_cell_background(painter, item, item.widget)
        paint_movement_cell(painter, item, option.rect, index)


def show_movements(table: QTableView) -> None:
    """Sets ``table`` up for the rows of a ``TransactionTableModel``: two lines a row,
    the fixed widths of every list of movements and the movement taking what is left.
    A ``SelectableTable`` keeps its check boxes and «⋯»."""
    if isinstance(table, SelectableTable):
        table.setItemDelegate(MovementRowDelegate(table))
    else:
        table.setItemDelegate(_MovementDelegate(table))
    table.verticalHeader().setDefaultSectionSize(RowRole.DOUBLE)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    header = table.horizontalHeader()
    for column in (DATE, BADGE, CATEGORY, AMOUNT):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
    header.setSectionResizeMode(MOVEMENT, QHeaderView.ResizeMode.Stretch)
    fit_movement_columns(table)
    if isinstance(table, SelectableTable):
        # The title over the category's name, not over its dot.
        table.indent_title(CATEGORY, ControlSize.DOT_SMALL + Space.S)
    table.installEventFilter(_ColumnFitter(table))
    model = table.model()
    if isinstance(model, TransactionTableModel):

        def keep_sort_off_badge(column: int, _order: Qt.SortOrder) -> None:
            """A click on the initials' empty title leaves the order and its arrow as
            they were."""
            if column == BADGE:
                header.setSortIndicator(model.sort_column, model.sort_order)

        header.sortIndicatorChanged.connect(keep_sort_off_badge)


class _ColumnFitter(QObject):
    """Narrows the category in a narrow list and widens it back, as the table resizes."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Resize and isinstance(watched, QTableView):
            fit_movement_columns(watched)
        return False


def fit_movement_columns(table: QTableView) -> None:
    """The fixed widths, with room for the check box and the «⋯» in a
    ``SelectableTable``; the category narrows in a narrow list, and in one narrower
    still the category and then the initials step aside for the movement."""
    controls = isinstance(table, SelectableTable)
    header = table.horizontalHeader()
    padding = 2 * Space.S
    category = (
        Layout.MOVEMENT_CATEGORY_WIDTH
        if table.width() >= Layout.NARROW_LIST_WIDTH
        else Layout.MOVEMENT_CATEGORY_NARROW_WIDTH
    )
    check = Layout.CHECK_COLUMN - Space.S if controls else 0
    more = Layout.MORE_COLUMN - Space.S if controls else 0
    header.resizeSection(DATE, check + Layout.MOVEMENT_DATE_WIDTH + padding)
    header.resizeSection(BADGE, ControlSize.BADGE + padding)
    header.resizeSection(CATEGORY, category + padding)
    header.resizeSection(AMOUNT, Layout.MOVEMENT_AMOUNT_WIDTH + padding + more)
    drop_columns_to_fit(table, (CATEGORY, BADGE))


class CompactMovementRow(QWidget):
    """A movement where a table has no room, such as the Inicio's latest movements: the
    initial, the movement and the amount with the date under it. It draws row ``row`` of
    ``model`` with ``paint_movement_cell``, as Transacciones draws it, so the two always
    look alike; it answers as a row there too: a double click runs its main action and a
    right click opens ``actions_for()``.
    """

    def __init__(
        self,
        model: TransactionTableModel,
        row: int,
        actions_for: Callable[[], list[RowAction]],
    ) -> None:
        super().__init__()
        self.model = model
        self.row = row
        self.item = model.item(row)
        self.setFixedHeight(RowRole.DOUBLE)
        install_row_actions(self, actions_for)
        make_hoverable(self)

    def cells(self) -> dict[int, QRect]:
        """Where each column goes: the initial and the amount as wide as they need, and
        the movement in between."""
        rect = self.rect()
        badge = ControlSize.BADGE + 2 * Space.S
        amount = self._amount_width() + 2 * Space.S
        return {
            BADGE: QRect(rect.left(), rect.top(), badge, rect.height()),
            MOVEMENT: QRect(
                rect.left() + badge, rect.top(), rect.width() - badge - amount, rect.height()
            ),
            AMOUNT: QRect(rect.right() - amount + 1, rect.top(), amount, rect.height()),
        }

    def tooltip_at(self, position: QPoint) -> str:
        """The tooltip of the cell under ``position``, as a table gives each cell its own."""
        for column, cell in self.cells().items():
            if cell.contains(position):
                tooltip = self.model.index(self.row, column).data(Qt.ItemDataRole.ToolTipRole)
                return str(tooltip or "")
        return ""

    def event(self, event: QEvent) -> bool:
        if isinstance(event, QHelpEvent) and event.type() == QEvent.Type.ToolTip:
            text = self.tooltip_at(event.pos())
            if text:
                QToolTip.showText(event.globalPos(), text, self)
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().event(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        option = QStyleOption()
        option.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)
        cell_option = QStyleOptionViewItem()
        for column, cell in self.cells().items():
            paint_movement_cell(painter, cell_option, cell, self.model.index(self.row, column))
        painter.end()

    def _amount_width(self) -> int:
        """As wide as the amount or the date under it, so the movement keeps the rest."""
        index = self.model.index(self.row, AMOUNT)
        first = QFontMetrics(role_font(TextRole.STRONG)).horizontalAdvance(str(index.data()))
        second = QFontMetrics(role_font(TextRole.NOTE)).horizontalAdvance(
            str(index.data(SECOND_LINE_ROLE) or "")
        )
        return max(first, second) + 1
