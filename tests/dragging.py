"""Helpers to drag rows in tests, as the mouse would."""

from PySide6.QtCore import QMimeData, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QWidget


def send_drop(target: QWidget, mime: QMimeData, y: float) -> bool:
    """Drags ``mime`` over ``target`` and drops it at height ``y``; returns whether the
    target took the drop."""
    point = QPointF(20, y)
    args = (Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier(0))
    QApplication.sendEvent(target, QDragEnterEvent(point, *args))
    QApplication.sendEvent(target, QDragMoveEvent(point, *args))
    drop = QDropEvent(point, *args)
    QApplication.sendEvent(target, drop)
    return drop.isAccepted()
