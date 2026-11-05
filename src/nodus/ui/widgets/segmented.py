"""Row of mutually exclusive options, like a tab bar for a form."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QFrame):
    """Buttons of which exactly one is checked; emits ``changed`` with its index."""

    changed = Signal(int)

    def __init__(self, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedControl")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self.buttons: list[QPushButton] = []
        for index, label in enumerate(labels):
            button = QPushButton(label)
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._reserve_bold_width(button)
            self._group.addButton(button, index)
            layout.addWidget(button)
            self.buttons.append(button)
        self.buttons[0].setChecked(True)
        self._group.idToggled.connect(lambda index, checked: checked and self.changed.emit(index))

    # Horizontal padding of a segment in the stylesheet (QPushButton#Segment), plus a margin.
    SEGMENT_PADDING = 2 * 14 + 4

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
