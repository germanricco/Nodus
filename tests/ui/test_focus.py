"""The focus ring shows while moving with Tab, never after a click, and moves nothing."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from nodus.ui.dialogs.tag_dialogs import TagDialog

BUTTON_STYLES = ["PrimaryButton", "SecondaryButton", "SmallButton", "DangerButton"]
# Buttons with a ring of their own: the sidebar, segments and tabs.
RINGED = [*BUTTON_STYLES, "NavButton", "Segment", "Tab"]


def row_with(qtbot, style: str) -> tuple[QWidget, QLineEdit, QPushButton]:
    row = QWidget()
    qtbot.addWidget(row)
    layout = QHBoxLayout(row)
    field = QLineEdit()
    button = QPushButton("Guardar cambios")
    button.setObjectName(style)
    layout.addWidget(field)
    layout.addWidget(button)
    row.show()
    qtbot.waitExposed(row)
    row.activateWindow()
    qtbot.waitUntil(row.isActiveWindow)
    field.setFocus()
    return row, field, button


@pytest.mark.parametrize("style", BUTTON_STYLES)
def test_a_button_takes_the_focus_from_tab_only(qtbot, theme_manager, style):
    _row, field, button = row_with(qtbot, style)

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert not button.hasFocus()

    qtbot.keyClick(field, Qt.Key.Key_Tab)
    assert button.hasFocus()


@pytest.mark.parametrize("style", RINGED)
def test_the_focus_ring_keeps_the_button_size(qtbot, theme_manager, style):
    _row, field, button = row_with(qtbot, style)
    size = button.sizeHint()

    qtbot.keyClick(field, Qt.Key.Key_Tab)
    button.style().unpolish(button)
    button.style().polish(button)

    assert button.hasFocus()
    assert button.sizeHint() == size


def test_a_form_opens_in_its_first_field_not_on_its_button(qtbot, services, event_bus):
    dialog = TagDialog(services, event_bus)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.activateWindow()
    qtbot.waitUntil(dialog.isActiveWindow)

    assert dialog.focusWidget() is dialog.name_input


def test_the_window_opens_with_no_button_focused(qtbot, window):
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)

    assert not isinstance(window.focusWidget(), QPushButton)


def test_closing_ayuda_leaves_no_button_focused(qtbot, window):
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    window.toggle_help()

    window.toggle_help()

    assert not isinstance(window.focusWidget(), QPushButton)
