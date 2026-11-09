"""The «⋯» button and right-click menu shared by every list."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QMenu, QWidget

from nodus.ui.theme.theme import DARK, LIGHT, ThemeMode
from nodus.ui.theme.theme_manager import active_theme
from nodus.ui.widgets.row_actions import MoreButton, RowAction, build_menu, install_row_actions


def sample_actions(log: list[str]) -> list[RowAction]:
    return [
        RowAction("Editar", lambda: log.append("edit"), "pencil"),
        RowAction("Archivar", lambda: log.append("archive"), "archive", enabled=False),
        RowAction("Eliminar", lambda: log.append("delete"), "trash", destructive=True),
    ]


def test_menu_lists_the_actions_with_the_destructive_ones_apart(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    log: list[str] = []

    menu = build_menu(parent, sample_actions(log))

    items = menu.actions()
    assert [a.text() for a in items] == ["Editar", "Archivar", "", "Eliminar"]
    assert items[2].isSeparator()
    assert not items[1].isEnabled()
    assert all(not a.icon().isNull() for a in items if not a.isSeparator())
    items[0].trigger()
    items[3].trigger()
    assert log == ["edit", "delete"]


def test_more_button_opens_the_menu_built_at_that_moment(qtbot):
    state = {"paused": False}

    def actions():
        return [RowAction("Reanudar" if state["paused"] else "Pausar", lambda: None)]

    button = MoreButton(actions)
    qtbot.addWidget(button)
    button.show()

    state["paused"] = True
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert button.menu is not None and button.menu.isVisible()
    assert [a.text() for a in button.menu.actions()] == ["Reanudar"]
    assert button.toolTip() == "Más acciones"
    button.menu.close()


def test_right_click_opens_the_same_menu(qtbot):
    row = QWidget()
    qtbot.addWidget(row)
    row.show()
    log: list[str] = []
    install_row_actions(row, lambda: sample_actions(log))

    row.customContextMenuRequested.emit(QPoint(5, 5))

    menus = [m for m in row.findChildren(QMenu) if m.isVisible()]
    assert len(menus) == 1
    assert [a.text() for a in menus[0].actions() if not a.isSeparator()] == [
        "Editar",
        "Archivar",
        "Eliminar",
    ]
    menus[0].close()


def test_active_theme_follows_the_theme_manager(theme_manager):
    assert active_theme() is LIGHT
    theme_manager.set_mode(ThemeMode.DARK)
    assert active_theme() is DARK
    theme_manager.set_mode(ThemeMode.LIGHT)
