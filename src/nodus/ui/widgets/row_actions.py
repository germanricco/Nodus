"""The actions of a list row: the «⋯» button and the right-click menu, built the same way.

Every list shows a row's actions in one menu, opened from the «⋯» at its end or with a
right click, so the user finds them in the same place on every page. The menu is built
when it opens, from a function that returns the actions, so it always matches the row's
current state (paused or active, archived or not).

A row's main action (``RowAction.default``) is bold in its menu and runs on a double
click, as in Windows, so the double click and the menu never disagree.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QMenu, QPushButton, QWidget

from nodus.ui.theme.design import ControlSize, IconSize, Popup
from nodus.ui.theme.icons import icon as tinted_icon
from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme_manager import active_theme
from nodus.ui.widgets.style import make_hoverable

MORE_ACTIONS = "Más acciones"


@dataclass(frozen=True)
class RowAction:
    """One menu item: its text, what it does and an optional icon from ``ui/icons``.

    Destructive actions (delete, remove) go last, apart from the rest and with a red icon.
    ``default`` marks the row's main action: bold in the menu and run by a double click
    (or by a click, on rows that lead somewhere). Never a destructive one.
    """

    text: str
    callback: Callable[[], object]
    icon: str | None = None
    destructive: bool = False
    enabled: bool = True
    default: bool = False


ActionsFor = Callable[[], Sequence[RowAction]]


def default_action(actions: Sequence[RowAction]) -> RowAction | None:
    """The row's main action, if it has one."""
    defaults = [action for action in actions if action.default]
    assert len(defaults) <= 1, "A row has a single main action"
    assert not any(action.destructive for action in defaults), "Never a destructive one"
    return defaults[0] if defaults else None


def run_default(actions: Sequence[RowAction]) -> bool:
    """Runs the row's main action, if it has one and it is enabled; says whether it ran."""
    action = default_action(actions)
    if action is None or not action.enabled:
        return False
    action.callback()
    return True


def build_menu(parent: QWidget, actions: Sequence[RowAction]) -> QMenu:
    """A menu with ``actions``, a separator before the destructive ones and the main
    action in bold."""
    main = default_action(actions)
    theme = active_theme()
    menu = QMenu(parent)
    menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    previous: RowAction | None = None
    for action in actions:
        if action.destructive and previous is not None and not previous.destructive:
            menu.addSeparator()
        item = menu.addAction(action.text)
        if action.icon is not None:
            color = theme.expense if action.destructive else theme.text_muted
            item.setIcon(tinted_icon(action.icon, color))
        item.setEnabled(action.enabled)
        item.triggered.connect(lambda _checked=False, run=action.callback: run())
        if action is main:
            menu.setDefaultAction(item)
        previous = action
    return menu


def release_hover(widget: QWidget) -> None:
    """Turns off the light of the row under a menu that closed, unless the mouse is still
    on it. While a menu is open it holds the mouse, so Qt never tells the row the mouse
    left, and the row would stay lit after the menu closes elsewhere."""
    row = _hoverable_row(widget)
    if row is None or row.rect().contains(row.mapFromGlobal(QCursor.pos())):
        return
    row.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
    row.update()


def _hoverable_row(widget: QWidget | None) -> QWidget | None:
    while widget is not None and not widget.property("hoverable"):
        widget = widget.parentWidget()
    return widget


def show_menu(parent: QWidget, actions: Sequence[RowAction], position: QPoint) -> QMenu:
    """Opens the menu of ``actions`` at ``position`` (global) without blocking."""
    menu = build_menu(parent, actions)
    menu.popup(position)
    return menu


def install_row_actions(widget: QWidget, actions_for: ActionsFor) -> None:
    """What every row with actions does, the same on every page: it lights up under the
    mouse, a right click anywhere on it opens the menu of ``actions_for()`` and a double
    click runs its main action."""
    make_hoverable(widget)
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    handler = _RowHandler(widget, actions_for)
    widget.customContextMenuRequested.connect(handler.open_menu)
    widget.installEventFilter(handler)


class _RowHandler(QObject):
    """Lives with the row: opens its menu on a right click, turns its light off when the
    menu closes elsewhere, and runs its main action on a double click (the labels inside
    the row let the click through to it).

    The menu's signal goes to a slot of this object, not to a lambda or to the menu,
    which is deleted on close: Qt then crashes calling into it."""

    def __init__(self, row: QWidget, actions_for: ActionsFor) -> None:
        super().__init__(row)
        self._row = row
        self._actions_for = actions_for

    def open_menu(self, position: QPoint) -> None:
        menu = show_menu(self._row, self._actions_for(), self._row.mapToGlobal(position))
        menu.aboutToHide.connect(self.release_hover)

    def release_hover(self) -> None:
        release_hover(self._row)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.MouseButtonDblClick
            and event.button() == Qt.MouseButton.LeftButton
        ):
            return run_default(self._actions_for())
        return False


class MoreButton(QPushButton):
    """The «⋯» at the end of a row. A click opens the menu of ``actions_for()`` under it,
    aligned to its right edge so it never covers the row's text."""

    SIZE = ControlSize.SMALL_BUTTON

    def __init__(self, actions_for: ActionsFor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._actions_for = actions_for
        self.menu: QMenu | None = None
        self.setObjectName("MoreButton")
        self.setToolTip(MORE_ACTIONS)
        self.setAccessibleName(MORE_ACTIONS)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setIconSize(QSize(IconSize.L, IconSize.L))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.open_menu)
        self._tint()

    def actions_list(self) -> Sequence[RowAction]:
        return self._actions_for()

    def open_menu(self) -> None:
        self.menu = build_menu(self, self._actions_for())
        corner = self.mapToGlobal(self.rect().bottomRight())
        self.menu.popup(
            QPoint(corner.x() - self.menu.sizeHint().width(), corner.y() + Popup.MENU_OFFSET)
        )
        self.menu.aboutToHide.connect(self._release_row)

    def _release_row(self) -> None:
        """The row under the menu turns its light off if the mouse left it meanwhile."""
        release_hover(self)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._tint()

    def _tint(self) -> None:
        """Muted at rest and in the text color under the mouse, in the current theme."""
        theme = active_theme()
        result = QIcon(tinted_pixmap("more", theme.text_muted))
        result.addPixmap(tinted_pixmap("more", theme.text), QIcon.Mode.Active)
        self.setIcon(result)
