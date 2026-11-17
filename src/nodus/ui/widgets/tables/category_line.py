"""A row led by a color dot and a name, that lights up and can be clicked."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from nodus.ui.theme.design import ControlSize, Space
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.elided_label import ElidedLabel
from nodus.ui.widgets.style import set_style_property


class CategoryLine(QFrame):
    """A row with a color dot and a category name, then any widgets on the right.

    It lights up under the mouse (or when ``set_highlighted`` says so) and can be clicked,
    so the donut legend and the comparison list lead to the category's transactions.
    """

    hovered = Signal(bool)
    clicked = Signal()

    def __init__(self, color: str, name: str, detail: str = "", clickable: bool = True) -> None:
        super().__init__()
        self.setObjectName("CategoryLine")
        self.name = name
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
        self._layout = layout
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Ver sus transacciones")

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
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
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
