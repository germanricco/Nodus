"""Base for the pages about one item: an account, a payee or a tag."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from nodus.ui.navigation import DetailId
from nodus.ui.pages.page import Page
from nodus.ui.theme.design import Space
from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager

BACK_BUTTON_SIZE = 36
BACK_ICON_SIZE = 20


class DetailPage(Page):
    """A page about one item, opened from its list: the arrow left of the title, or Esc,
    goes back, as the Back button of Windows apps.

    Subclasses fill the page for the item ``show_item`` sets, in ``refresh``. When the item
    no longer exists (deleted or merged), the page goes back to its list.
    """

    back_requested = Signal()

    def __init__(self, detail_id: DetailId, theme_manager: ThemeManager) -> None:
        super().__init__("")
        self.detail_id = detail_id
        self.item_id: int | None = None
        self.back_button = QPushButton()
        self.back_button.setObjectName("BackButton")
        self.back_button.setFixedSize(BACK_BUTTON_SIZE, BACK_BUTTON_SIZE)
        self.back_button.setIconSize(QSize(BACK_ICON_SIZE, BACK_ICON_SIZE))
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        label = detail_id.list_page.label
        self.back_button.setToolTip(f"Volver a {label} (Esc)")
        self.back_button.setAccessibleName(f"Volver a {label}")
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
        if event.key() == Qt.Key.Key_Escape:
            self.back_requested.emit()
            return
        super().keyPressEvent(event)


def danger_zone(text: str, action: str, run: Callable[[], object]) -> tuple[QFrame, QPushButton]:
    """A card with a red border at the foot of a detail page, apart from the everyday
    actions, that explains what deleting takes with it; the button still asks first."""
    card = QFrame()
    card.setObjectName("DangerZone")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(Space.XL, Space.L, Space.XL, Space.L)
    layout.setSpacing(Space.S)
    title = QLabel("ZONA DE PELIGRO")
    title.setObjectName("CardTitle")
    explanation = QLabel(text)
    explanation.setObjectName("FieldHint")
    explanation.setWordWrap(True)
    button = QPushButton(action)
    button.setObjectName("DangerButton")
    button.clicked.connect(run)
    layout.addWidget(title)
    layout.addWidget(explanation)
    layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
    return card, button
