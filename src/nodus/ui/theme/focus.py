"""Buttons take the focus only from the keyboard.

Qt's stylesheets have no ``:focus-visible``: ``:focus`` also lights up after a click.
Giving buttons ``Qt.TabFocus`` instead of ``Qt.StrongFocus`` makes the two the same, so
the focus ring shows while moving with Tab and never stays behind a click.

Qt also hands the focus to a button by itself: when the page holding it goes away (a
search field, a table, a record's page), the next page's first button gets it, and its
ring lights up with no key pressed. And when the window comes back (on starting, on
closing a dialog, with Alt+Tab) or a menu closes, Qt gives the focus to the widget that
had it or, with none, to the first one that takes it. Such a button, or a row that
answers the keyboard, lets the focus go again unless the keyboard had taken it there
(``KeyboardOnly``).

The style also makes every button and check box at least ``ControlSize.TARGET`` tall, so
a link or a box is as easy to hit as the rest (WCAG 2.2, 2.5.8).
"""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QAbstractButton, QApplication, QProxyStyle, QPushButton, QWidget

from nodus.ui.theme.design import ControlSize
from nodus.ui.theme.hover import HoverLift
from nodus.ui.theme.wheel import WheelGuard

# How the keyboard moves the focus: Tab and a shortcut. Any other way is Qt's or the code's.
KEYBOARD_REASONS = {
    Qt.FocusReason.TabFocusReason,
    Qt.FocusReason.BacktabFocusReason,
    Qt.FocusReason.ShortcutFocusReason,
}
# Giving the focus back where it was, as a window coming back or a menu closing does: right
# only for the widget the keyboard had left it on.
GIVEN_BACK_REASONS = {
    Qt.FocusReason.ActiveWindowFocusReason,
    Qt.FocusReason.PopupFocusReason,
}


class KeyboardOnly(QObject):
    """Takes the focus back from a widget the keyboard did not move it to, once the move
    is over, so no ring is left on a button or a row nobody chose."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Where the keyboard went last; only compared, so it may be gone by then.
        self._chosen: QWidget | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if not (
            event.type() == QEvent.Type.FocusIn
            and isinstance(event, QFocusEvent)
            and isinstance(watched, QWidget)
        ):
            return False
        reason = event.reason()
        if reason in KEYBOARD_REASONS:
            self._chosen = watched
        elif not (reason in GIVEN_BACK_REASONS and watched is self._chosen):
            QTimer.singleShot(0, watched, lambda: _let_go(watched))
        return False


def _let_go(widget: QWidget) -> None:
    if widget.hasFocus():
        widget.clearFocus()


class KeyboardFocusStyle(QProxyStyle):
    """Fusion, with every push button that takes the focus on a click taking it only
    from Tab and letting go of it when nobody moved it there (``KeyboardOnly``), rising
    under the mouse (``HoverLift``), and the mouse wheel guarded (``WheelGuard``). A
    style sees each widget once, as it gets its look (``polish``), which is far cheaper
    than watching every event of the application."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self._wheel = WheelGuard(self)
        self.keyboard_only = KeyboardOnly(self)
        self._hover_lift = HoverLift(self)

    def polish(self, widget: QWidget) -> None:  # type: ignore[override]
        super().polish(widget)
        if isinstance(widget, QPushButton) and widget.focusPolicy() == Qt.FocusPolicy.StrongFocus:
            widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        if isinstance(widget, QPushButton) and widget.focusPolicy() == Qt.FocusPolicy.TabFocus:
            widget.installEventFilter(self.keyboard_only)
        if isinstance(widget, QPushButton):
            widget.installEventFilter(self._hover_lift)  # it rises if it is ``LIFTED``
        if isinstance(widget, QAbstractButton):
            # Once the stylesheet gave it its padding, which comes after this.
            QTimer.singleShot(0, widget, partial(_raise_to_target, widget))
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


def keyboard_only(widget: QWidget) -> None:
    """Lets ``widget`` keep the focus only when the keyboard took it there, as buttons
    do (a row that answers the keyboard, which the style does not see as a button)."""
    if _style is not None:
        widget.installEventFilter(_style.keyboard_only)


def _raise_to_target(button: QAbstractButton) -> None:
    """Only a button shorter than the target: a minimum replaces the natural height as the
    least a layout leaves it, so a taller one would be squeezed down to it in a short
    window instead of scrolling."""
    if (
        button.sizeHint().height() < ControlSize.TARGET <= button.maximumHeight()
        and button.minimumHeight() < ControlSize.TARGET
    ):
        button.setMinimumHeight(ControlSize.TARGET)
