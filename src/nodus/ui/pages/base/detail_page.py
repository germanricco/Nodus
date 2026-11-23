"""Base for the pages about one item: an account, a payee or a tag."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPushButton

from nodus.i18n import _
from nodus.ui.navigation import DetailId
from nodus.ui.pages.base.page import Page
from nodus.ui.shortcuts import BACK_TO_LIST
from nodus.ui.theme.design import ControlSize, IconSize, Space
from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager


class DetailPage(Page):
    """A page about one item, opened from its list: the arrow left of the title, or Esc,
    goes back, as the Back button of Windows apps.

    Subclasses fill the page for the item ``show_item`` sets, in ``refresh``. When the item
    no longer exists (deleted or merged), the page goes back to its list.
    """

    back_requested = Signal()
    # A movement to add from the page's empty list, with the item already in it.
    new_transaction_requested = Signal(object)  # TransactionStart

    def __init__(self, detail_id: DetailId, theme_manager: ThemeManager) -> None:
        super().__init__("")
        self.detail_id = detail_id
        self.item_id: int | None = None
        self.back_button = QPushButton()
        self.back_button.setObjectName("BackButton")
        self.back_button.setFixedSize(ControlSize.BACK_BUTTON, ControlSize.BACK_BUTTON)
        self.back_button.setIconSize(QSize(IconSize.XL, IconSize.XL))
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        label = detail_id.list_page.label
        self.back_button.setToolTip(_("Volver a {page} (Esc)").format(page=label))
        self.back_button.setAccessibleName(_("Volver a {page}").format(page=label))
        self.back_button.clicked.connect(self.back_requested)
        self._header.insertWidget(0, self.back_button)
        self._header.insertSpacing(1, Space.XS)
        self._set_back_icon(theme_manager.theme)
        theme_manager.theme_changed.connect(self._set_back_icon)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def show_item(self, item_id: int) -> None:
        """Fills the page for ``item_id``; the caller shows it."""
        self.item_id = item_id
        self.refresh()

    def _set_back_icon(self, theme: Theme) -> None:
        self.back_button.setIcon(icon("arrow-left", theme.text))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        # Reaches the page when no child used it, e.g. a table with no chosen rows.
        if BACK_TO_LIST.matches(event):
            self.back_requested.emit()
            return
        super().keyPressEvent(event)
