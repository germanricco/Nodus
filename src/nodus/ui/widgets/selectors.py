"""Combo boxes to pick an account, a category, a payee or a tag.

As filters, they can end with an «Editar» row that leads to the page managing the list.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QFont, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from nodus.models.account import Account
from nodus.models.payee import Payee
from nodus.models.tag import Tag
from nodus.services.category_service import CategoryNode
from nodus.ui.widgets.color import color_icon

# Item data: a section heading ("Gastos") instead of a choice, and how deep a choice is.
HEADING_ROLE = Qt.ItemDataRole.UserRole + 1
DEPTH_ROLE = Qt.ItemDataRole.UserRole + 2
# The closing «Editar» row: an action, not a choice.
MANAGE_ROLE = Qt.ItemDataRole.UserRole + 3
MANAGE_LABEL = "Editar"

_Index = QModelIndex | QPersistentModelIndex


class _SectionDelegate(QStyledItemDelegate):
    """Draws the list of a selector: headings as small gray titles followed by a line, and
    subcategories shifted in with their color dot, so the tree reads at a glance. The
    «Editar» row goes under a line, in the accent color, so it reads as an action."""

    INDENT = 18
    HEADING_GAP = 8  # space above every heading but the first row
    MANAGE_GAP = 9  # space above the «Editar» row, with the line in its middle

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: _Index) -> None:
        if index.data(HEADING_ROLE):
            self._paint_heading(painter, option, index)
            return
        if index.data(MANAGE_ROLE):
            self._paint_manage(painter, option, index)
            return
        depth = index.data(DEPTH_ROLE) or 0
        if depth:
            option = QStyleOptionViewItem(option)
            option.rect = option.rect.adjusted(depth * self.INDENT, 0, 0, 0)
        super().paint(painter, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: _Index) -> QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        if index.data(HEADING_ROLE) and index.row() > 0:
            size.setHeight(size.height() + self.HEADING_GAP)
        elif index.data(MANAGE_ROLE):
            size.setHeight(size.height() + self.MANAGE_GAP)
        return size

    def _paint_heading(
        self, painter: QPainter, option: QStyleOptionViewItem, index: _Index
    ) -> None:
        painter.save()
        font = QFont(option.font)
        font.setPointSizeF(font.pointSizeF() * 0.85)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        color = option.palette.color(QPalette.ColorRole.PlaceholderText)
        painter.setPen(color)
        rect = option.rect.adjusted(8, self.HEADING_GAP if index.row() > 0 else 0, -8, 0)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        line_start = rect.left() + painter.fontMetrics().horizontalAdvance(text) + 8
        color.setAlpha(90)
        painter.setPen(color)
        middle = rect.center().y()
        painter.drawLine(line_start, middle, rect.right(), middle)
        painter.restore()

    def _paint_manage(self, painter: QPainter, option: QStyleOptionViewItem, index: _Index) -> None:
        painter.save()
        line = option.palette.color(QPalette.ColorRole.PlaceholderText)
        line.setAlpha(90)
        painter.setPen(line)
        middle = option.rect.top() + self.MANAGE_GAP // 2
        painter.drawLine(option.rect.left() + 8, middle, option.rect.right() - 8, middle)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        # The application palette: the list's own Highlight is the soft selection color.
        painter.setPen(QApplication.palette().color(QPalette.ColorRole.Highlight))
        rect = option.rect.adjusted(8, self.MANAGE_GAP, -8, 0)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()


class _SelectorComboBox(QComboBox):
    """A combo box whose items carry an id, with an optional first item meaning "any".

    With ``enable_manage_item``, the list ends with an «Editar» row. Clicking it closes the
    list and emits ``manage_requested`` without changing the selection.
    """

    manage_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._has_manage_item = False
        self.setMinimumContentsLength(14)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setItemDelegate(_SectionDelegate(self))
        self.view().pressed.connect(self._on_item_pressed)

    def enable_manage_item(self) -> None:
        """Ends the list with «Editar» from the next time it is filled."""
        self._has_manage_item = True

    def showPopup(self) -> None:  # noqa: N802
        """Opens the list as wide as its longest name, so no name is cut off."""
        view = self.view()
        view.setMinimumWidth(view.sizeHintForColumn(0) + _SectionDelegate.INDENT + 24)
        super().showPopup()

    def current_id(self) -> int | None:
        """The selected item's id; None for the "any" item or an empty list."""
        return self.currentData()

    def select(self, item_id: int | None) -> None:
        """Selects the item with ``item_id``; falls back to the first selectable item."""
        index = next(
            (
                i for i in range(self.count())
                if self.itemData(i) == item_id and self._is_choice(i)
            ),
            self._first_selectable(),
        )  # fmt: skip
        self.setCurrentIndex(index)

    def _start(self, all_label: str | None) -> int | None:
        """Clears the items, adds the "any" item if wanted, and returns the previous id."""
        previous = self.current_id()
        self.clear()
        if all_label:
            self.addItem(all_label, None)
        return previous

    def _fill(self, items: Iterable[tuple[str, int]], all_label: str | None) -> None:
        """Replaces the list with ``items`` (name, id), keeping the selection."""
        self.blockSignals(True)
        previous = self._start(all_label)
        for name, item_id in items:
            self.addItem(name, item_id)
        self._finish(previous)

    def _finish(self, previous: int | None) -> None:
        """Closes a refill started with ``_start``: adds «Editar» if enabled, lets signals
        through again and restores the selection."""
        if self._has_manage_item:
            self.addItem(MANAGE_LABEL, None)
            item = self.model().item(self.count() - 1)
            # Enabled to take the click, but not selectable, so it never becomes the filter.
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setData(True, MANAGE_ROLE)
        self.blockSignals(False)
        self.select(previous)

    def _add_heading(self, text: str) -> None:
        """A title that separates sections; it cannot be chosen."""
        self.addItem(text.upper(), None)
        item = self.model().item(self.count() - 1)
        item.setEnabled(False)
        item.setData(True, HEADING_ROLE)

    def _first_selectable(self) -> int:
        return next((i for i in range(self.count()) if self._is_choice(i)), -1)

    def _is_choice(self, index: int) -> bool:
        """Whether the row at ``index`` can be selected: not a heading nor «Editar»."""
        item = self.model().item(index)
        return item.isEnabled() and not item.data(MANAGE_ROLE)

    def _on_item_pressed(self, index: QModelIndex) -> None:
        if index.data(MANAGE_ROLE):
            self.hidePopup()
            self.manage_requested.emit()


class AccountComboBox(_SelectorComboBox):
    """Lists accounts by name; remembers the selection when the list is reloaded."""

    def set_accounts(self, accounts: list[Account], all_label: str | None = None) -> None:
        self._accounts = {account.id: account for account in accounts}
        self._fill(((account.name, account.id) for account in accounts), all_label)

    def current_account(self) -> Account | None:
        account_id = self.current_id()
        return None if account_id is None else self._accounts[account_id]


class PayeeComboBox(_SelectorComboBox):
    """Lists payees by name; remembers the selection when the list is reloaded."""

    def set_payees(self, payees: list[Payee], all_label: str | None = None) -> None:
        self._fill(((payee.name, payee.id) for payee in payees), all_label)


class TagComboBox(_SelectorComboBox):
    """Lists tags by name with their color; remembers the selection when reloaded."""

    def set_tags(self, tags: list[Tag], all_label: str | None = None) -> None:
        self._fill(((tag.name, tag.id) for tag in tags), all_label)
        colors = {tag.id: tag.color for tag in tags}
        for index in range(self.count()):
            tag_id = self.itemData(index)
            if tag_id is not None:
                self.setItemIcon(index, color_icon(colors[tag_id]))


class CategoryComboBox(_SelectorComboBox):
    """Lists categories as a tree: color dot, parents, then their indented subcategories.

    ``sections`` pairs an optional heading with the tree under it, so one list can show
    expense and income categories apart.
    """

    def set_categories(
        self,
        sections: list[tuple[str | None, list[CategoryNode]]],
        all_label: str | None = None,
    ) -> None:
        self.blockSignals(True)
        previous = self._start(all_label)
        for heading, nodes in sections:
            if heading:
                self._add_heading(heading)
            for node in nodes:
                self.addItem(color_icon(node.category.color), node.category.name, node.category.id)
                for child in node.children:
                    self.addItem(color_icon(child.color), child.name, child.id)
                    self.setItemData(self.count() - 1, 1, DEPTH_ROLE)
        self._finish(previous)
