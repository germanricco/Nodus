"""Small helpers shared by widgets."""

from PySide6.QtWidgets import QLayout, QWidget


def set_style_property(widget: QWidget, name: str, value: object) -> None:
    """Sets a property the stylesheet selects on (e.g. ``QLabel[tone="negative"]``).

    Qt does not re-evaluate stylesheets when a property changes, so the widget is re-polished.
    """
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def clear_layout(layout: QLayout) -> None:
    """Removes and deletes every widget in ``layout``, so it can be rebuilt from fresh data."""
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())
