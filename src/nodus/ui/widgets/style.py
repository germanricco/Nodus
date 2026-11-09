"""Small helpers shared by widgets."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLayout, QWidget


def set_style_property(widget: QWidget, name: str, value: object) -> None:
    """Sets a property the stylesheet selects on (e.g. ``QLabel[tone="negative"]``).

    Qt does not re-evaluate stylesheets when a property changes, so the widget is re-polished.
    """
    widget.setProperty(name, value)
    _repolish(widget)


def make_hoverable(widget: QWidget) -> None:
    """Lights up ``widget``'s background under the mouse, as the sidebar's items do, so a
    row that can be clicked or has a menu shows it responds (``[hoverable="true"]`` in the
    stylesheet). Only for such rows: a row that lights up but does nothing misleads."""
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    widget.setAttribute(Qt.WidgetAttribute.WA_Hover)
    widget.setProperty("hoverable", True)


def set_style_name(widget: QWidget, name: str) -> None:
    """Gives ``widget`` the object name the stylesheet selects on (e.g. ``#ErrorLabel``)."""
    if widget.objectName() != name:
        widget.setObjectName(name)
        _repolish(widget)


def _repolish(widget: QWidget) -> None:
    """Qt does not re-evaluate stylesheets on its own when a selector's input changes."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def clear_layout(layout: QLayout) -> None:
    """Removes and deletes every widget in ``layout``, so it can be rebuilt from fresh data."""
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            # deleteLater waits for the event loop; hiding now keeps stale widgets out of sight.
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())
