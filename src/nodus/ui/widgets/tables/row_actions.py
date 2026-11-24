"""The actions of a list row: the «⋯» button and the right-click menu, built the same way.

Every list shows a row's actions in one menu, opened from the «⋯» at its end or with a
right click, so the user finds them in the same place on every page. The menu is built
when it opens, from a function that returns the actions, so it always matches the row's
current state (paused or active, archived or not).

A row's main action (``RowAction.default``) is bold in its menu and runs on a double
click, as in Windows, so the double click and the menu never disagree. A row that leads
somewhere (an account, a goal, a notification) runs it on a single click instead.

With the keyboard (the ``ROWS`` group of ``shortcuts.py``), Tab reaches the row, ↑ and ↓
move to the rows around it, Enter runs its main action and the Menu key or Mayús+F10
opens its menu; a row that folds (a category with subcategories) folds with ← and
unfolds with →.

Every action declares what a click does (``Effect``), so none changes data by surprise:
what changes it at once can be undone or reversed from the same menu, and what destroys
it asks first.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QIcon, QKeyEvent
from PySide6.QtWidgets import QLabel, QMenu, QPushButton, QScrollArea, QWidget

from nodus.i18n import N_, _
from nodus.ui.shortcuts import (
    FOLD_ROW,
    NEXT_ROW,
    OPEN_ROW,
    PREVIOUS_ROW,
    ROW_MENU,
    UNFOLD_ROW,
)
from nodus.ui.theme.design import ControlSize, IconSize, Popup
from nodus.ui.theme.focus import keyboard_only
from nodus.ui.theme.icons import icon as tinted_icon
from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme_manager import active_theme
from nodus.ui.widgets.style import make_hoverable, set_style_property

MORE_ACTIONS = N_("Más acciones")


def open_cue() -> QLabel:
    """The «›» that ends every row that opens a page, with the light under the mouse and
    the hand: the three signs of a row that leads somewhere. Hidden, it keeps its room,
    so the rows of a list line up whether they open or not."""
    cue = QLabel("›")
    cue.setObjectName("OpenCue")
    set_style_property(cue, "muted", True)
    policy = cue.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    cue.setSizePolicy(policy)
    return cue


class Effect(Enum):
    """What a click on an action does to the data."""

    OPEN = "open"  # goes to a page or opens a dialog: nothing changes yet
    UNDOABLE = "undoable"  # changes it at once and offers «Deshacer»
    TOGGLE = "toggle"  # changes it at once; the opposite is in the same menu (Archivar)
    CONFIRMED = "confirmed"  # asks before changing it


@dataclass(frozen=True)
class RowAction:
    """One menu item: its text, what it does and an optional icon from ``ui/icons``.

    Destructive actions (delete, remove) go last, apart from the rest and with a red icon.
    ``default`` marks the row's main action: bold in the menu and run by a double click
    (or by a click, on rows that lead somewhere). Never a destructive one.
    ``effect`` is required: a destructive action always asks first.
    """

    text: str
    callback: Callable[[], object]
    icon: str | None = None
    destructive: bool = False
    enabled: bool = True
    default: bool = False
    effect: Effect = field(kw_only=True)

    def __post_init__(self) -> None:
        assert not self.destructive or self.effect is Effect.CONFIRMED, (
            f"«{self.text}» destroys data, so it asks first"
        )


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


def install_row_actions(
    widget: QWidget,
    actions_for: ActionsFor,
    open_on_click: str | None = None,
    fold: Callable[[bool], None] | None = None,
) -> None:
    """What every row with actions does, the same on every page: it lights up under the
    mouse, a right click anywhere on it opens the menu of ``actions_for()`` and a double
    click runs its main action. It answers the keyboard too (see the module).

    With ``open_on_click``, the tooltip that says where it leads ("Abrir la cuenta"), a
    single click runs it instead, with the hand cursor. With ``fold``, ← calls it with
    ``True`` and → with ``False``."""
    make_hoverable(widget)
    widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    # Only from the keyboard, as buttons (theme/focus.py): a click leaves no ring.
    widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    keyboard_only(widget)
    widget.setProperty(KEYBOARD_ROW, True)
    if open_on_click:
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setToolTip(open_on_click)
    handler = _RowHandler(widget, actions_for, bool(open_on_click), fold)
    widget.customContextMenuRequested.connect(handler.open_menu)
    widget.installEventFilter(handler)
    # Its «⋯» opens the same menu: one stop of Tab per row is enough.
    for more in widget.findChildren(MoreButton):
        more.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    _give_back_focus(widget)


KEYBOARD_ROW = "keyboardRow"  # the property of a row that answers the keyboard


def rows_beside(row: QWidget) -> list[QWidget]:
    """The rows that answer the keyboard in ``row``'s window, shown, top to bottom."""
    rows = [
        widget
        for widget in row.window().findChildren(QWidget)
        if widget.property(KEYBOARD_ROW) and widget.isVisible()
    ]

    def place(widget: QWidget) -> tuple[int, int]:
        corner = widget.mapToGlobal(QPoint())
        return corner.y(), corner.x()

    return sorted(rows, key=place)


def row_identity(row: QWidget) -> str:
    """What tells a row from the others in its list: its first text (a name)."""
    for label in row.findChildren(QLabel):
        if label.text():
            return label.text()
    return ""


# The row the keyboard was on when its page rebuilt it, by its identity: a page refreshes
# by building its rows again (after a change, a fold, a move), and the keyboard would be
# thrown out of the list each time.
_lost_row: list[str] = []


def _keep_lost_row(identity: str) -> None:
    _lost_row[:] = [identity]
    # Only for the rebuild that follows, not for a row that shows up much later.
    QTimer.singleShot(1000, _lost_row.clear)


def _give_back_focus(row: QWidget) -> None:
    """Gives the keyboard to a new row that replaces the one it was on."""
    if _lost_row and _lost_row[0] == row_identity(row):
        _lost_row.clear()
        QTimer.singleShot(0, row, lambda: focus_row(row))


def focus_row(row: QWidget) -> None:
    """Moves the keyboard to ``row``, scrolled into view."""
    parent = row.parentWidget()
    while parent is not None and not isinstance(parent, QScrollArea):
        parent = parent.parentWidget()
    if parent is not None:
        parent.ensureWidgetVisible(row)
    row.setFocus(Qt.FocusReason.TabFocusReason)


def spoken_name(row: QWidget) -> str:
    """What a screen reader says for ``row``: its texts, left to right."""
    labels = [label for label in row.findChildren(QLabel) if label.isVisible() and label.text()]
    labels.sort(key=lambda label: (label.mapTo(row, QPoint()).x(), label.mapTo(row, QPoint()).y()))
    return ", ".join(label.text() for label in labels if not label.text().startswith("<"))


class _RowHandler(QObject):
    """Lives with the row: opens its menu on a right click, turns its light off when the
    menu closes elsewhere, and runs its main action on a double click (the labels inside
    the row let the click through to it).

    The menu's signal goes to a slot of this object, not to a lambda or to the menu,
    which is deleted on close: Qt then crashes calling into it."""

    def __init__(
        self,
        row: QWidget,
        actions_for: ActionsFor,
        open_on_click: bool,
        fold: Callable[[bool], None] | None,
    ) -> None:
        super().__init__(row)
        self._row = row
        self._actions_for = actions_for
        self._open_on_click = open_on_click
        self._fold = fold
        self._identity = ""
        self._after_double_click = False

    def actions_list(self) -> Sequence[RowAction]:
        return self._actions_for()

    def open_menu(self, position: QPoint) -> None:
        menu = show_menu(self._row, self._actions_for(), self._row.mapToGlobal(position))
        menu.aboutToHide.connect(self.release_hover)

    def release_hover(self) -> None:
        release_hover(self._row)

    def _key(self, event: QKeyEvent) -> bool:
        """Runs what a key asks of the row; whether it was one of the row's keys."""
        if OPEN_ROW.matches(event):
            run_default(self._actions_for())
        elif ROW_MENU.matches(event):
            self.open_menu(QPoint(self._row.width() // 2, self._row.height()))
        elif PREVIOUS_ROW.matches(event) or NEXT_ROW.matches(event):
            rows = rows_beside(self._row)
            index = rows.index(self._row) + (-1 if PREVIOUS_ROW.matches(event) else 1)
            if 0 <= index < len(rows):
                focus_row(rows[index])
        elif self._fold is not None and (FOLD_ROW.matches(event) or UNFOLD_ROW.matches(event)):
            self._fold(FOLD_ROW.matches(event))
        else:
            return False
        return True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            return self._key(event)
        if kind == QEvent.Type.FocusIn:
            self._row.setAccessibleName(spoken_name(self._row))
            self._identity = row_identity(self._row)
        elif kind == QEvent.Type.Hide and self._row.hasFocus():
            # Hidden, with the keyboard on it, by a rebuild of its page (Qt tells the
            # hide before it moves the focus away).
            _keep_lost_row(self._identity)
        if kind not in (QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseButtonRelease):
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if not self._open_on_click:
            return kind == QEvent.Type.MouseButtonDblClick and run_default(self._actions_for())
        # The first click already ran it: the double click, and the release that
        # follows it, are swallowed so it does not run again.
        if kind == QEvent.Type.MouseButtonDblClick:
            self._after_double_click = True
            return True
        if self._after_double_click:
            self._after_double_click = False
            return True
        if not self._row.rect().contains(event.position().toPoint()):
            return False  # pressed on the row, but let go elsewhere: no click
        return run_default(self._actions_for())


class MoreButton(QPushButton):
    """The «⋯» at the end of a row. A click opens the menu of ``actions_for()`` under it,
    aligned to its right edge so it never covers the row's text."""

    SIZE = ControlSize.SMALL_BUTTON

    def __init__(self, actions_for: ActionsFor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._actions_for = actions_for
        self.menu: QMenu | None = None
        self.setObjectName("MoreButton")
        self.setToolTip(_(MORE_ACTIONS))
        self.setAccessibleName(_(MORE_ACTIONS))
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
