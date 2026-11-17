"""The mouse wheel scrolls what the user is looking at, never two things at once.

Pages scroll as a whole, and some hold a scrolling list of their own (the movements of an
account). Qt hands the wheel to the page as soon as the list reaches its end, so a single
turn moved both. And a list, a date or a number under the mouse took the wheel and changed
its value while the user only meant to scroll the page past it.

``WheelGuard`` fixes both for every widget, present or future: the style puts it on each
one as it gets its look (``KeyboardFocusStyle.polish``), so no page has to remember it.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QScrollBar,
    QWidget,
)

# Controls whose value the wheel changes: only once the user is working on them.
VALUE_CONTROLS = (QComboBox, QAbstractSpinBox, QAbstractSlider)


def is_value_control(widget: QWidget) -> bool:
    return isinstance(widget, VALUE_CONTROLS) and not isinstance(widget, QScrollBar)


class WheelGuard(QObject):
    """Watches the wheel on value controls and on the viewport of scrolling views.

    A value control without the focus, inside something that scrolls, lets the wheel
    scroll that instead; alone in a popup it works as always. A view
    inside a scrolling page keeps the wheel while it can scroll that way, even at its
    end, so the page does not move with it.
    """

    def guard(self, widget: QWidget) -> None:
        """Called as ``widget`` gets its look; installing twice keeps a single filter."""
        if is_value_control(widget):
            # By default a list takes the focus on a wheel turn, before anyone sees it.
            if widget.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            widget.installEventFilter(self)
        elif isinstance(widget, QAbstractScrollArea):
            widget.viewport().installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() != QEvent.Type.Wheel or not isinstance(watched, QWidget):
            return False
        if is_value_control(watched):
            area = enclosing_area(watched)
            if watched.hasFocus() or area is None:  # nothing to scroll past it
                return False
            QApplication.sendEvent(bar_for(area, event), event)
            return keep(event)  # the value stays as it was
        view = watched.parentWidget()
        if isinstance(view, QAbstractScrollArea) and enclosing_area(view) is not None:
            bar = bar_for(view, event)
            if bar.maximum() > bar.minimum():
                QApplication.sendEvent(bar, event)
                return keep(event)
        return False


def keep(event: QEvent) -> bool:
    """Stops the event here. Handling it is not enough: Qt hands a wheel turn nobody
    accepted to the parent, as a scroll bar at its end leaves it."""
    event.accept()
    return True


def enclosing_area(widget: QWidget) -> QAbstractScrollArea | None:
    """The nearest scrolling area ``widget`` sits in, such as the page."""
    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QAbstractScrollArea):
        parent = parent.parentWidget()
    return parent


def bar_for(area: QAbstractScrollArea, event: QWheelEvent) -> QScrollBar:
    """The scroll bar a wheel turn moves: the horizontal one for a sideways turn."""
    delta = event.angleDelta()
    if abs(delta.x()) > abs(delta.y()):
        return area.horizontalScrollBar()
    return area.verticalScrollBar()
