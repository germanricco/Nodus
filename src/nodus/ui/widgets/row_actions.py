"""The actions of a list row: the «⋯» button and the right-click menu, built the same way.

Every list shows a row's actions in one menu, opened from the «⋯» at its end or with a
right click, so the user finds them in the same place on every page. The menu is built
when it opens, from a function that returns the actions, so it always matches the row's
current state (paused or active, archived or not).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QPushButton, QWidget

from nodus.ui.theme.icons import icon as tinted_icon
from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme_manager import active_theme

MORE_ACTIONS = "Más acciones"


@dataclass(frozen=True)
class RowAction:
    """One menu item: its text, what it does and an optional icon from ``ui/icons``.

    Destructive actions (delete, remove) go last, apart from the rest and with a red icon.
    """

    text: str
    callback: Callable[[], object]
    icon: str | None = None
    destructive: bool = False
    enabled: bool = True


ActionsFor = Callable[[], Sequence[RowAction]]


def build_menu(parent: QWidget, actions: Sequence[RowAction]) -> QMenu:
    """A menu with ``actions``, a separator before the destructive ones."""
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
        previous = action
    return menu


def show_menu(parent: QWidget, actions: Sequence[RowAction], position: QPoint) -> QMenu:
    """Opens the menu of ``actions`` at ``position`` (global) without blocking."""
    menu = build_menu(parent, actions)
    menu.popup(position)
    return menu


def install_context_menu(widget: QWidget, actions_for: ActionsFor) -> None:
    """A right click anywhere on ``widget`` opens the menu of ``actions_for()``."""
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    widget.customContextMenuRequested.connect(
        lambda position: show_menu(widget, actions_for(), widget.mapToGlobal(position))
    )


class MoreButton(QPushButton):
    """The «⋯» at the end of a row. A click opens the menu of ``actions_for()`` under it,
    aligned to its right edge so it never covers the row's text."""

    SIZE = 28

    def __init__(self, actions_for: ActionsFor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._actions_for = actions_for
        self.menu: QMenu | None = None
        self.setObjectName("MoreButton")
        self.setToolTip(MORE_ACTIONS)
        self.setAccessibleName(MORE_ACTIONS)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.open_menu)
        self._tint()

    def actions_list(self) -> Sequence[RowAction]:
        return self._actions_for()

    def open_menu(self) -> None:
        self.menu = build_menu(self, self._actions_for())
        corner = self.mapToGlobal(self.rect().bottomRight())
        self.menu.popup(QPoint(corner.x() - self.menu.sizeHint().width(), corner.y() + 2))

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
