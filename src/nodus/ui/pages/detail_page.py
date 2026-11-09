"""Base for the pages about one item: an account, a payee or a tag."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from nodus.ui.navigation import DetailId
from nodus.ui.pages.page import Page
from nodus.ui.theme.design import Space


class DetailPage(Page):
    """A page about one item, opened from its list: «‹ Cuentas» on top, or Esc, go back.

    Subclasses fill the page for the item ``show_item`` sets, in ``refresh``. When the item
    no longer exists (deleted or merged), the page goes back to its list.
    """

    back_requested = Signal()

    def __init__(self, detail_id: DetailId) -> None:
        super().__init__("")
        self.detail_id = detail_id
        self.item_id: int | None = None
        self.back_button = QPushButton(f"‹ {detail_id.list_page.label}")
        self.back_button.setObjectName("LinkButton")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.back_requested)
        self.layout().insertWidget(0, self.back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def show_item(self, item_id: int) -> None:
        """Fills the page for ``item_id``; the caller shows it."""
        self.item_id = item_id
        self.refresh()

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
