"""Category and tag colors: a dot to show one and a picker to choose one."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QPushButton, QWidget

from nodus.models.palette import PALETTE
from nodus.ui.theme.design import ControlSize, Line, Space
from nodus.ui.widgets.color_wheel import ColorWheelPopup, hue_ring_gradient


def color_icon(color: str, size: int = 12) -> QIcon:
    """A filled circle in ``color``, for item views and combo boxes that take icons."""
    return colors_icon([color], size)


def colors_icon(colors: list[str], size: int = 12) -> QIcon:
    """Filled circles in ``colors``, side by side, as a cell with several tags shows them."""
    gap = size // 3
    pixmap = QPixmap(len(colors) * (size + gap) - gap, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    for index, color in enumerate(colors):
        painter.setBrush(QColor(color))
        painter.drawEllipse(index * (size + gap), 0, size, size)
    painter.end()
    return QIcon(pixmap)


class ColorSwatch(QPushButton):
    """A color to choose in the picker: a filled circle, ringed in the text color when
    it is the chosen one."""

    def __init__(self, color: str, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color = color
        self.setCheckable(True)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("color", color)
        self.setToolTip(color)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        if self.isChecked():
            # The ring takes the outer edge and the color fills what is left inside it,
            # so no edge of the color shows past the ring.
            painter.setBrush(self.palette().windowText())
            painter.drawEllipse(circle)
            inset = Line.THICK
            circle = circle.adjusted(inset, inset, -inset, -inset)
        painter.setBrush(QColor(self.color))
        painter.drawEllipse(circle)
        painter.end()


class WheelSwatch(QPushButton):
    """The last swatch of the picker: a ring of every hue with a «+», which opens the
    color wheel."""

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2
        painter.setPen(Qt.PenStyle.NoPen)
        # A ring, so the dialog's own background shows through in either theme.
        ring = QPainterPath()
        ring.addEllipse(center, radius, radius)
        ring.addEllipse(center, radius - 4, radius - 4)
        painter.fillPath(ring, QBrush(hue_ring_gradient(center)))
        painter.setPen(QPen(self.palette().windowText(), Line.STROKE))
        arm = radius / 3
        painter.drawLine(
            QPointF(center.x() - arm, center.y()), QPointF(center.x() + arm, center.y())
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - arm), QPointF(center.x(), center.y() + arm)
        )
        painter.end()


class ColorPicker(QWidget):
    """A grid of round swatches; exactly one is selected. The last one, «+», opens a
    color wheel for any other color.

    A color outside the palette (set with ``set_color`` or chosen on the wheel) gets its
    own swatch, so editing never silently changes a category's color.
    """

    SWATCH_SIZE = ControlSize.COLOR_SWATCH
    COLUMNS = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(Space.S)
        self._group = QButtonGroup(self)
        self._swatches: dict[str, QPushButton] = {}
        self.wheel_swatch = WheelSwatch()
        self.wheel_swatch.setFixedSize(self.SWATCH_SIZE, self.SWATCH_SIZE)
        self.wheel_swatch.setCursor(Qt.CursorShape.PointingHandCursor)
        self.wheel_swatch.setToolTip("Otro color")
        self.wheel_swatch.clicked.connect(self.open_wheel)
        self.wheel_popup: ColorWheelPopup | None = None
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

    def open_wheel(self) -> None:
        """Opens the color wheel on the current color, under the «+» swatch."""
        self.wheel_popup = ColorWheelPopup(self.color(), self)
        self.wheel_popup.color_chosen.connect(self.set_color)
        self.wheel_popup.open_below(self.wheel_swatch)

    def _add_swatch(self, color: str) -> None:
        swatch = ColorSwatch(color, self.SWATCH_SIZE)
        index = len(self._swatches)
        self._grid.addWidget(swatch, index // self.COLUMNS, index % self.COLUMNS)
        self._group.addButton(swatch)
        self._swatches[color] = swatch
        # The «+» always comes right after the last color.
        self._grid.removeWidget(self.wheel_swatch)
        self._grid.addWidget(
            self.wheel_swatch, (index + 1) // self.COLUMNS, (index + 1) % self.COLUMNS
        )
