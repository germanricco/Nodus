"""A row led by a color dot and a name, that lights up and can lead to a page."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from nodus.ui.navigation import RecordLink
from nodus.ui.theme.design import ControlSize, Space
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.elided_label import ElidedLabel
from nodus.ui.widgets.style import set_style_property
from nodus.ui.widgets.tables.row_actions import open_cue


class CategoryLine(QFrame):
    """A row with a color dot and a name (a category, payee or tag), then any widgets on
    the right.

    With a ``link`` it leads to that record's page: it lights up under the mouse, shows
    the hand and ends in «›», and a click emits ``opened``. Without one it shows none of
    the three, but keeps the room of the «›» so a list of both kinds lines up.
    ``set_highlighted`` lights it up from outside, as the donut does with its legend.
    """

    hovered = Signal(bool)
    opened = Signal(object)  # RecordLink

    def __init__(
        self, color: str, name: str, detail: str = "", link: RecordLink | None = None
    ) -> None:
        super().__init__()
        self.setObjectName("CategoryLine")
        self.name = name
        self.link = link
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.XS, Space.S, Space.XS)
        layout.setSpacing(Space.S)
        layout.addWidget(ColorDot(color, size=ControlSize.DOT_SMALL))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(ElidedLabel(name))
        if detail:
            detail_label = ElidedLabel(detail)
            set_style_property(detail_label, "muted", True)
            texts.addWidget(detail_label)
        layout.addLayout(texts, stretch=1)
        self.cue = open_cue()
        layout.addWidget(self.cue)
        # Hidden once in the row: shown before it has a parent, it would flash as a window.
        self.cue.setHidden(link is None)
        self._layout = layout
        if link is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(link.detail.open_text)
            self.hovered.connect(self.set_highlighted)

    def add(self, widget: QWidget) -> QWidget:
        """Adds ``widget`` on the right, before the «›»."""
        self._layout.insertWidget(self._layout.indexOf(self.cue), widget)
        return widget

    def set_highlighted(self, highlighted: bool) -> None:
        set_style_property(self, "highlighted", highlighted)

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802
        super().enterEvent(event)
        self.hovered.emit(True)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.hovered.emit(False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if (
            self.link is not None
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.opened.emit(self.link)
