"""Buttons take the focus only from the keyboard.

Qt's stylesheets have no ``:focus-visible``: ``:focus`` also lights up after a click.
Giving buttons ``Qt.TabFocus`` instead of ``Qt.StrongFocus`` makes the two the same, so
the focus ring shows while moving with Tab and never stays behind a click.

Qt also hands the focus to a button by itself: when the page holding it goes away (a
search field, a table, a record's page), the next page's first button gets it, and its
ring lights up with no key pressed. Such a button lets the focus go again
(``KeyboardOnly``).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QApplication, QProxyStyle, QPushButton, QWidget

from nodus.ui.theme.wheel import WheelGuard

# How the person moves the focus: Tab, a shortcut, a menu closing back onto its button, or
# coming back to the window where they left it. Any other way is Qt's or the code's.
PERSON_REASONS = {
    Qt.FocusReason.TabFocusReason,
    Qt.FocusReason.BacktabFocusReason,
    Qt.FocusReason.ShortcutFocusReason,
    Qt.FocusReason.PopupFocusReason,
    Qt.FocusReason.ActiveWindowFocusReason,
}


class KeyboardOnly(QObject):
    """Takes the focus back from a button the person did not move it to, once the move
    is over, so no ring is left on a button nobody chose."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.FocusIn
            and isinstance(event, QFocusEvent)
            and event.reason() not in PERSON_REASONS
            and isinstance(watched, QWidget)
        ):
            QTimer.singleShot(0, watched, lambda: _let_go(watched))
        return False


def _let_go(widget: QWidget) -> None:
    if widget.hasFocus():
        widget.clearFocus()


class KeyboardFocusStyle(QProxyStyle):
    """Fusion, with every push button that takes the focus on a click taking it only
    from Tab and letting go of it when nobody moved it there (``KeyboardOnly``), and the
    mouse wheel guarded (``WheelGuard``). A style sees each widget
    once, as it gets its look (``polish``), which is far cheaper than watching every
    event of the application."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self._wheel = WheelGuard(self)
        self._keyboard_only = KeyboardOnly(self)

    def polish(self, widget: QWidget) -> None:  # type: ignore[override]
        super().polish(widget)
        if isinstance(widget, QPushButton) and widget.focusPolicy() == Qt.FocusPolicy.StrongFocus:
            widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        if isinstance(widget, QPushButton) and widget.focusPolicy() == Qt.FocusPolicy.TabFocus:
            widget.installEventFilter(self._keyboard_only)
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
