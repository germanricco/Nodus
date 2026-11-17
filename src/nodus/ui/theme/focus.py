"""Buttons take the focus only from the keyboard.

Qt's stylesheets have no ``:focus-visible``: ``:focus`` also lights up after a click.
Giving buttons ``Qt.TabFocus`` instead of ``Qt.StrongFocus`` makes the two the same, so
the focus ring shows while moving with Tab and never stays behind a click.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProxyStyle, QPushButton, QWidget

from nodus.ui.theme.wheel import WheelGuard


class KeyboardFocusStyle(QProxyStyle):
    """Fusion, with every push button that takes the focus on a click taking it only
    from Tab, and the mouse wheel guarded (``WheelGuard``). A style sees each widget
    once, as it gets its look (``polish``), which is far cheaper than watching every
    event of the application."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self._wheel = WheelGuard(self)

    def polish(self, widget: QWidget) -> None:  # type: ignore[override]
        super().polish(widget)
        if isinstance(widget, QPushButton) and widget.focusPolicy() == Qt.FocusPolicy.StrongFocus:
            widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._wheel.guard(widget)


_style: KeyboardFocusStyle | None = None


def use_keyboard_focus_style(app: QApplication) -> None:
    """Gives ``app`` the style once. Replacing it would delete the one in use, which
    widgets still point to (with a stylesheet, ``app.style()`` is no longer it, so the
    module remembers it instead)."""
    global _style
    if _style is None:
        _style = KeyboardFocusStyle("Fusion")
        app.setStyle(_style)
