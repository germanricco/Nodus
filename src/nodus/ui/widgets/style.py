"""Small helpers shared by widgets."""

from PySide6.QtWidgets import QLayout, QWidget


def set_style_property(widget: QWidget, name: str, value: object) -> None:
    """Sets a property the stylesheet selects on (e.g. ``QLabel[tone="negative"]``).

    Qt does not re-evaluate stylesheets when a property changes, so the widget is re-polished.
    """
    widget.setProperty(name, value)
    _repolish(widget)


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
