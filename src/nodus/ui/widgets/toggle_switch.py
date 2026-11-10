"""On/off switch for settings that take effect at once."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from nodus.ui.theme.design import ControlSize, Line, Opacity
from nodus.ui.theme.theme_manager import active_theme


class ToggleSwitch(QAbstractButton):
    """A pill whose knob slides right and fills with the accent when on, as in the Windows
    settings. It goes at the right of a ``SettingRow``, where the title says what it turns
    on; a checkbox would put the control on the left, away from the other controls."""

    WIDTH = ControlSize.TOGGLE_WIDTH
    HEIGHT = ControlSize.TOGGLE_HEIGHT
    KNOB_MARGIN = 4  # geometry: the knob inside its track

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.sizeHint())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.WIDTH, self.HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        theme = active_theme()
        on = self.isChecked()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(Opacity.DISABLED)
        track = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        radius = track.height() / 2
        if on:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.accent))
        else:
            painter.setPen(QPen(QColor(theme.text_muted), Line.STROKE))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(track, radius, radius)

        size = self.HEIGHT - 2 * self.KNOB_MARGIN
        x = self.WIDTH - self.KNOB_MARGIN - size if on else self.KNOB_MARGIN
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.on_accent if on else theme.text_muted))
        painter.drawEllipse(QRectF(x, self.KNOB_MARGIN, size, size))
        if self.hasFocus():
            painter.setPen(QPen(QColor(theme.accent), Line.THIN))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(track, radius, radius)
