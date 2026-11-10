"""A color wheel to choose any color, beyond the palette's swatches."""

from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QRegularExpression, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from nodus.ui.theme.design import ControlSize, Layout, Popup, Space

# Positions of the brightness slider; enough steps for every value of a hex digit pair.
VALUE_STEPS = 1000
PREVIEW_SIZE = ControlSize.COLOR_PREVIEW
HEX_PATTERN = QRegularExpression("#?[0-9a-fA-F]{0,6}")


def hue_ring_gradient(center: QPointF) -> QConicalGradient:
    """Every hue around ``center``, red at three o'clock going counterclockwise, as the
    wheel and the picker's «+» swatch draw it."""
    gradient = QConicalGradient(center, 0)
    for step in range(7):
        position = step / 6
        gradient.setColorAt(position, QColor.fromHsvF(position % 1.0, 1.0, 1.0))
    return gradient


class HueSaturationWheel(QWidget):
    """A disc where the angle is the hue and the distance from the center the saturation.

    Brightness comes from outside (``set_value``) and darkens the whole disc, so the disc
    always shows what each point would give.
    """

    changed = Signal()
    SIZE = ControlSize.COLOR_WHEEL

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.hue = 0.0
        self.saturation = 0.0
        self.value = 1.0

    def set_hsv(self, hue: float, saturation: float, value: float) -> None:
        self.hue, self.saturation, self.value = hue, saturation, value
        self.update()

    def pick(self, point: QPointF) -> None:
        """Takes the hue and saturation under ``point``; outside the disc, its edge."""
        center, radius = self._center(), self._radius()
        dx, dy = point.x() - center.x(), center.y() - point.y()  # y grows downwards
        self.hue = (math.degrees(math.atan2(dy, dx)) % 360) / 360
        self.saturation = min(1.0, math.hypot(dx, dy) / radius)
        self.update()
        self.changed.emit()

    def marker_position(self) -> QPointF:
        """Where the current hue and saturation sit on the disc."""
        center, angle = self._center(), self.hue * 2 * math.pi
        distance = self.saturation * self._radius()
        return QPointF(
            center.x() + math.cos(angle) * distance, center.y() - math.sin(angle) * distance
        )

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _radius(self) -> float:
        return min(self.width(), self.height()) / 2 - 2

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.pick(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.pick(event.position())

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        center, radius = self._center(), self._radius()
        painter.setBrush(QBrush(hue_ring_gradient(center)))
        painter.drawEllipse(center, radius, radius)
        # Saturation fades towards white at the center…
        whiten = QRadialGradient(center, radius)
        whiten.setColorAt(0, QColor(255, 255, 255, 255))
        whiten.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(whiten))
        painter.drawEllipse(center, radius, radius)
        # …and brightness darkens everything evenly.
        painter.setBrush(QColor(0, 0, 0, round(255 * (1 - self.value))))
        painter.drawEllipse(center, radius, radius)
        marker = self.marker_position()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#000000"), 3))
        painter.drawEllipse(marker, 6, 6)
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(marker, 6, 6)
        painter.end()


class ColorWheelPopup(QFrame):
    """A popup with the wheel, a brightness slider, a preview and the hex code.

    The three stay in step: moving one updates the others. ``color_chosen`` carries the
    color as "#rrggbb" when the user accepts it.
    """

    color_chosen = Signal(str)

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("ColorWheelPopup")
        # A code set or typed is kept as is, since going through HSV may shift a digit.
        self._exact: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.L, Space.L, Space.L, Space.L)
        layout.setSpacing(Space.M)

        self.wheel = HueSaturationWheel()
        self.wheel.changed.connect(self._on_wheel_changed)
        layout.addWidget(self.wheel, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.value_slider = QSlider(Qt.Orientation.Horizontal)
        self.value_slider.setRange(0, VALUE_STEPS)
        self.value_slider.setToolTip("Brillo")
        self.value_slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.value_slider)

        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.hex_input = QLineEdit()
        self.hex_input.setValidator(QRegularExpressionValidator(HEX_PATTERN, self.hex_input))
        self.hex_input.setFixedWidth(Layout.HEX_FIELD_WIDTH)
        self.hex_input.textEdited.connect(self._on_hex_edited)
        code = QHBoxLayout()
        code.setSpacing(Space.S)
        code.addWidget(self.preview)
        code.addWidget(self.hex_input)
        code.addStretch()
        layout.addLayout(code)

        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.close)
        self.accept_button = QPushButton("Usar color")
        self.accept_button.setObjectName("PrimaryButton")
        self.accept_button.clicked.connect(self._accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.accept_button)
        layout.addLayout(buttons)

        self.set_color(color)

    def color(self) -> str:
        if self._exact is not None:
            return self._exact
        return QColor.fromHsvF(self.wheel.hue, self.wheel.saturation, self.wheel.value).name()

    def set_color(self, color: str) -> None:
        """Moves every control to ``color``."""
        self._move_to(color)
        self._sync(update_hex=True)

    def _move_to(self, color: str) -> None:
        """Puts the wheel on ``color``; a gray keeps hue 0, since it has none."""
        hue, saturation, value, _alpha = QColor(color).getHsvF()
        self.wheel.set_hsv(max(hue, 0.0), saturation, value)
        self._exact = QColor(color).name()

    def open_below(self, anchor: QWidget) -> None:
        """Shows the popup under ``anchor``, its left edge aligned with the anchor's."""
        self.adjustSize()
        self.move(anchor.mapToGlobal(QPoint(0, anchor.height() + Popup.PANEL_OFFSET)))
        self.show()
        self.hex_input.setFocus()

    def _on_wheel_changed(self) -> None:
        self._exact = None
        self._sync(update_hex=True)

    def _on_value_changed(self, position: int) -> None:
        self._exact = None
        self.wheel.set_hsv(self.wheel.hue, self.wheel.saturation, position / VALUE_STEPS)
        self._sync(update_hex=True)

    def _on_hex_edited(self, text: str) -> None:
        """A complete code moves the wheel; the text stays as typed."""
        code = text if text.startswith("#") else f"#{text}"
        if len(code) == 7:
            self._move_to(code)
            self._sync(update_hex=False)
        self.accept_button.setEnabled(len(code) == 7)

    def _sync(self, update_hex: bool) -> None:
        """Brings the slider, the preview and, unless the user is typing it, the code in
        line with the wheel."""
        self.value_slider.blockSignals(True)
        self.value_slider.setValue(round(self.wheel.value * VALUE_STEPS))
        self.value_slider.blockSignals(False)
        color = self.color()
        self.preview.setStyleSheet(f"background: {color}; border-radius: {PREVIEW_SIZE // 2}px;")
        if update_hex:
            self.hex_input.setText(color)
            self.accept_button.setEnabled(True)

    def _accept(self) -> None:
        self.close()
        self.color_chosen.emit(self.color())
