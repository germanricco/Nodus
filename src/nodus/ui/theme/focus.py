"""Buttons take the focus only from the keyboard.

Qt's stylesheets have no ``:focus-visible``: ``:focus`` also lights up after a click.
Giving buttons ``Qt.TabFocus`` instead of ``Qt.StrongFocus`` makes the two the same, so
the focus ring shows while moving with Tab and never stays behind a click.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProxyStyle, QPushButton, QWidget


class KeyboardFocusStyle(QProxyStyle):
    """Fusion, with every push button that takes the focus on a click taking it only
    from Tab. A style sees each widget once, as it gets its look (``polish``), which is
    far cheaper than watching every event of the application."""

    def polish(self, widget: QWidget) -> None:  # type: ignore[override]
        super().polish(widget)
        if isinstance(widget, QPushButton) and widget.focusPolicy() == Qt.FocusPolicy.StrongFocus:
            widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
