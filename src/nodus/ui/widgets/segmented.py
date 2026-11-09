"""Rows of mutually exclusive options: a segmented control to pick an option or a
filter, and tabs to switch between the views of a page."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget

from nodus.ui.theme.design import Space


class SegmentedControl(QFrame):
    """Buttons of which exactly one is checked; emits ``changed`` with its index."""

    changed = Signal(int)

    # The stylesheet's selectors for the frame and its buttons.
    FRAME_NAME = "SegmentedControl"
    BUTTON_NAME = "Segment"
    MARGIN = Space.XS
    SPACING = Space.XXS

    def __init__(self, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(self.FRAME_NAME)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        layout.setSpacing(self.SPACING)
        self._group = QButtonGroup(self)
        self.buttons: list[QPushButton] = []
        for index, label in enumerate(labels):
            button = QPushButton(label)
            button.setObjectName(self.BUTTON_NAME)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._reserve_bold_width(button)
            self._group.addButton(button, index)
            layout.addWidget(button)
            self.buttons.append(button)
        self.buttons[0].setChecked(True)
        self._group.idToggled.connect(lambda index, checked: checked and self.changed.emit(index))

    # Horizontal padding of a segment in the stylesheet (QPushButton#Segment), plus a margin.
    SEGMENT_PADDING = 2 * Space.L + Space.XS

    def _reserve_bold_width(self, button: QPushButton) -> None:
        """The checked segment is bold, so each one is sized for its bold text; otherwise
        the label is cut off when it gets selected."""
        button.ensurePolished()
        bold = QFont(button.font())
        bold.setWeight(QFont.Weight.DemiBold)
        width = QFontMetrics(bold).horizontalAdvance(button.text())
        button.setMinimumWidth(width + self.SEGMENT_PADDING)

    def index(self) -> int:
        return self._group.checkedId()

    def set_index(self, index: int) -> None:
        self.buttons[index].setChecked(True)

    def set_segment_enabled(self, index: int, enabled: bool) -> None:
        self.buttons[index].setEnabled(enabled)

    def set_segment_visible(self, index: int, visible: bool) -> None:
        """Shows or hides an option that does not apply, instead of graying it out."""
        self.buttons[index].setVisible(visible)


class TabBar(SegmentedControl):
    """Tabs that switch between the views of a page, underlined when chosen, as the
    SelectorBar of Windows. Pages place them with ``Page.set_tabs``, under the title, so
    they never look like the segmented controls that pick an option or a filter."""

    FRAME_NAME = "TabBar"
    BUTTON_NAME = "Tab"
    MARGIN = 0
    SPACING = Space.XL
    SEGMENT_PADDING = 2 * Space.XXS + Space.XS
