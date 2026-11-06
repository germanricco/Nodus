"""Category colors: a dot to show one and a picker to choose one."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QLabel, QPushButton, QWidget

from nodus.models.palette import PALETTE


def color_icon(color: str, size: int = 12) -> QIcon:
    """A filled circle in ``color``, for item views and combo boxes that take icons."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return QIcon(pixmap)


class ColorDot(QLabel):
    """A small filled circle in a category's color."""

    def __init__(self, color: str, size: int = 12, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self.setStyleSheet(f"background: {color}; border-radius: {self.width() // 2}px;")


class ColorPicker(QWidget):
    """A grid of round swatches; exactly one is selected.

    A color outside the palette (set with ``set_color``) gets its own swatch, so editing
    never silently changes a category's color.
    """

    SWATCH_SIZE = 26
    COLUMNS = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        self._group = QButtonGroup(self)
        self._swatches: dict[str, QPushButton] = {}
        for color in PALETTE:
            self._add_swatch(color)
        self.set_color(PALETTE[0])

    def color(self) -> str:
        return self._group.checkedButton().property("color")

    def set_color(self, color: str) -> None:
        color = color.lower()
        if color not in self._swatches:
            self._add_swatch(color)
        self._swatches[color].setChecked(True)

    def _add_swatch(self, color: str) -> None:
        swatch = QPushButton()
        swatch.setCheckable(True)
        swatch.setFixedSize(self.SWATCH_SIZE, self.SWATCH_SIZE)
        swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        swatch.setProperty("color", color)
        swatch.setToolTip(color)
        radius = self.SWATCH_SIZE // 2
        swatch.setStyleSheet(
            f"QPushButton {{ background: {color}; border-radius: {radius}px; border: none; }}"
            f"QPushButton:checked {{ border: 3px solid palette(window-text); }}"
        )
        index = len(self._swatches)
        self._grid.addWidget(swatch, index // self.COLUMNS, index % self.COLUMNS)
        self._group.addButton(swatch)
        self._swatches[color] = swatch
