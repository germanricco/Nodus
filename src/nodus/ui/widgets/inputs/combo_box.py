"""The one combo box of the app, and the look of every list that opens over a page."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSize, Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QWidget,
)

from nodus.ui.theme.design import ControlSize, Line, Popup

LIST_POPUP = "ListPopup"
# What QComboBox.insertSeparator marks its separators with.
_SEPARATOR = "separator"

_Index = QModelIndex | QPersistentModelIndex


def paint_divider(painter: QPainter, option: QStyleOptionViewItem, y: int) -> None:
    """A soft line across a list at height ``y``, inset like the options' text."""
    painter.save()
    color = option.palette.color(QPalette.ColorRole.PlaceholderText)
    color.setAlpha(Line.SOFT_ALPHA)
    painter.setPen(color)
    side = Popup.LIST_ITEM_PADDING[1]
    painter.drawLine(option.rect.left() + side, y, option.rect.right() - side, y)
    painter.restore()


class ListPopupDelegate(QStyledItemDelegate):
    """Draws a list's options as the stylesheet says, and its separators as a line with
    ``Popup.DIVIDER_MARGIN`` above and below, like a menu's.

    Every option is one line of text high plus ``Popup.LIST_ITEM_PADDING``, with an icon
    or without: Qt makes a row with an icon a little taller, and a list of categories
    would read looser than the others.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: _Index) -> None:
        if _is_separator(index):
            paint_divider(painter, option, option.rect.center().y())
            return
        super().paint(painter, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: _Index) -> QSize:  # noqa: N802
        if _is_separator(index):
            return QSize(0, Popup.DIVIDER_HEIGHT)
        size = super().sizeHint(option, index)
        size.setHeight(option.fontMetrics.height() + 2 * Popup.LIST_ITEM_PADDING[0])
        return size


def _is_separator(index: _Index) -> bool:
    return index.data(Qt.ItemDataRole.AccessibleDescriptionRole) == _SEPARATOR


def style_as_list_popup(view: QAbstractItemView) -> None:
    """Gives ``view`` the look of every list over a page: the ``ListPopup`` rules of the
    stylesheet, spaced by ``Popup`` (design.py) like the menus.

    Qt draws a combo box's list with a menu delegate that ignores the stylesheet's item
    padding; a styled delegate follows it. A list that draws its own items (the
    selectors') sets its delegate afterwards.
    """
    view.setObjectName(LIST_POPUP)
    view.setItemDelegate(ListPopupDelegate(view))
    # Scrolling by whole options would leave part of a row empty at the end of a long
    # list, after its last option, instead of the frame's padding.
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)


class ComboBox(QComboBox):
    """A combo box whose list opens below it with the app's list look. Every combo box in
    Nodus is one of these, so a new one cannot miss the spacing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._narrows_to_label = False
        style_as_list_popup(self.view())

    def narrow_to_label(self) -> None:
        """Lets a filter narrow down to its first item, the label it shows when nothing
        is chosen («Cuenta», «Beneficiario»), so a row of filters fits a narrow window.
        Its list still opens as wide as its longest option."""
        self._narrows_to_label = True
        self.updateGeometry()

    def showPopup(self) -> None:  # noqa: N802
        """Opens the list at least as wide as its longest option, so every name reads
        whole there even when the box itself is narrower."""
        view = self.view()
        frame = 2 * (Popup.PADDING + Line.THIN)
        longest = view.sizeHintForColumn(0) + frame + ControlSize.SCROLL_BAR_WIDTH
        view.setMinimumWidth(max(longest, super().minimumSizeHint().width()))
        super().showPopup()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = super().minimumSizeHint()
        if not self._narrows_to_label or self.count() == 0:
            return hint
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        label = QSize(self.fontMetrics().horizontalAdvance(self.itemText(0)), hint.height())
        size = self.style().sizeFromContents(QStyle.ContentsType.CT_ComboBox, option, label, self)
        return QSize(min(hint.width(), size.width()), hint.height())
