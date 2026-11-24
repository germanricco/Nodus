"""A button rises under the mouse, as on the web.

Qt's stylesheets change a button's color on hover at once and cannot animate it, so the
color stays theirs; what moves is a soft shadow that grows and drops a little under the
button, which reads as the button coming up to meet the mouse, and sinks again while it is
held down. Only the buttons that stand for an action rise (``LIFTED``); icons, links and
row menus answer with their color alone.

The shadow is not an effect on the button: Qt cuts a widget's drawing at its parent's
edge, and most buttons sit in a row that ends where they do, so the shadow would end in a
straight line. A ``_Shadow`` paints it instead, in the first container with room for it,
around the button and never over it, and lets the mouse through. It exists only while it
shows. With «Reducir animaciones», nothing rises.
"""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import (
    QEvent,
    QMargins,
    QObject,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPaintEvent, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QPushButton,
    QWidget,
)

from nodus.ui.theme.design import Easing, Lift, Motion, Opacity, Radius, motion_ms

# The buttons that rise: an action of their own, not an icon, a link or a row's menu.
LIFTED = {"PrimaryButton", "SecondaryButton", "DangerButton"}

AT_REST, HELD, RAISED = 0.0, Lift.HELD, 1.0

# How far the shadow reaches past the button on every side: its blur, and its drop.
_REACH = QMargins(*[Lift.BLUR + Lift.OFFSET] * 4)


@cache
def _blurred(width: int, height: int, color: str) -> QPixmap:
    """The button's shape in ``color``, blurred, with ``_REACH`` around it: drawn once
    per size and theme, so a frame only paints it again with more or less opacity."""
    size = QSize(width, height)
    shape = QPixmap(size)
    shape.fill(Qt.GlobalColor.transparent)
    painter = QPainter(shape)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(shape.rect()), Radius.L, Radius.L)
    painter.end()
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(Lift.BLUR)
    blur.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item = QGraphicsPixmapItem(shape)
    item.setGraphicsEffect(blur)
    scene = QGraphicsScene()
    scene.addItem(item)
    image = QImage(size.grownBy(_REACH), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    around = QRectF(-_REACH.left(), -_REACH.top(), image.width(), image.height())
    scene.render(painter, QRectF(image.rect()), around)
    painter.end()
    return QPixmap.fromImage(image)


class _Shadow(QWidget):
    """The shadow of one button, in a container with room around it."""

    def __init__(self, button: QPushButton, host: QWidget) -> None:
        super().__init__(host)
        self._button = button
        self.height_ = AT_REST
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.follow()
        self.show()
        self.raise_()

    def follow(self) -> None:
        """Around the button wherever it is now, as the page scrolls."""
        top_left = self._button.mapTo(self.parentWidget(), QPoint(0, 0))
        self.setGeometry(QRect(top_left, self._button.size()).marginsAdded(_REACH))

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        if self.height_ <= 0:
            return
        button = QPainterPath()
        button.addRoundedRect(
            QRectF(QRect(QPoint(_REACH.left(), _REACH.top()), self._button.size())),
            Radius.L,
            Radius.L,
        )
        around = QPainterPath()
        around.addRect(QRectF(self.rect()))
        color = QApplication.palette().color(QPalette.ColorRole.Shadow).name()
        painter = QPainter(self)
        painter.setClipPath(around - button)  # never over the button itself
        painter.setOpacity(Opacity.LIFT * self.height_)
        shadow = _blurred(self._button.width(), self._button.height(), color)
        painter.drawPixmap(0, round(Lift.OFFSET * self.height_), shadow)
        painter.end()


def _host(button: QPushButton) -> QWidget:
    """The first container that holds the button with room for its shadow: its own row
    usually ends where the button does."""
    host = button.parentWidget()
    while host.parentWidget() is not None:
        area = QRect(button.mapTo(host, QPoint(0, 0)), button.size()).marginsAdded(_REACH)
        if host.rect().contains(area):
            break
        host = host.parentWidget()
    return host


class _Rise(QVariantAnimation):
    """How high one button is, from ``AT_REST`` (no shadow) to ``RAISED``."""

    def __init__(self, button: QPushButton) -> None:
        super().__init__(button)
        self._button = button
        self.shadow: _Shadow | None = None
        self.setEasingCurve(Easing.SETTLE)
        self.valueChanged.connect(self._draw)
        self.finished.connect(self._settle)

    @property
    def height(self) -> float:
        current = self.currentValue()
        return AT_REST if current is None else float(current)

    def go(self, height: float) -> None:
        start = self.height
        self.stop()
        if self.shadow is None:
            self.shadow = _Shadow(self._button, _host(self._button))
        self.setStartValue(start)
        self.setEndValue(height)
        self.setDuration(motion_ms(Motion.FAST))
        self.start()

    def drop(self) -> None:
        """No shadow at once, as when the button goes away with its page."""
        self.stop()
        if self.shadow is not None:
            self.shadow.deleteLater()
            self.shadow = None

    def _draw(self, height: float) -> None:
        if self.shadow is not None:
            self.shadow.height_ = height
            self.shadow.follow()
            self.shadow.update()

    def _settle(self) -> None:
        if self.endValue() == AT_REST:
            self.drop()


class HoverLift(QObject):
    """Raises a ``LIFTED`` button while the mouse is on it and lowers it while held."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if not isinstance(watched, QPushButton) or watched.objectName() not in LIFTED:
            return False
        kind = event.type()
        rise = rise_of(watched)
        if kind == QEvent.Type.Enter:
            if _can_rise(watched):
                (rise or _Rise(watched)).go(RAISED)
        elif rise is None:
            pass  # it never rose: nothing to lower
        elif kind == QEvent.Type.Hide:
            rise.drop()
        elif kind == QEvent.Type.Leave or not watched.isEnabled():
            rise.go(AT_REST)
        elif kind == QEvent.Type.MouseButtonPress:
            rise.go(HELD)
        elif kind == QEvent.Type.MouseButtonRelease:
            rise.go(RAISED if watched.underMouse() else AT_REST)
        return False


def rise_of(button: QPushButton) -> _Rise | None:
    """How high ``button`` is, once it has risen."""
    return button.findChild(_Rise)


def shadow_of(button: QPushButton) -> QWidget | None:
    """The shadow ``button`` casts now, if any."""
    rise = rise_of(button)
    return None if rise is None else rise.shadow


def _can_rise(button: QPushButton) -> bool:
    """Not with less motion, not disabled, and not a window of its own."""
    return motion_ms(Motion.FAST) > 0 and button.isEnabled() and button.parentWidget() is not None
