"""Closing a form with changes asks before discarding them; without changes it just
closes."""

import pytest
from PySide6.QtCore import Qt

from nodus.ui.dialogs import form_dialog
from nodus.ui.dialogs.tag_dialogs import TagDialog


@pytest.fixture
def answer(monkeypatch) -> list[tuple]:
    """Answers the question with what the test puts first in the list."""
    calls: list[tuple] = [False]

    def reply(_parent, title, text, action, cancel_text) -> bool:
        calls.append((title, action, cancel_text))
        return calls[0]

    monkeypatch.setattr(form_dialog, "confirm", reply)
    return calls


def shown_dialog(qtbot, services, event_bus, tag=None) -> TagDialog:
    dialog = TagDialog(services, event_bus, tag)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_without_changes_esc_closes_without_asking(qtbot, services, event_bus, answer):
    dialog = shown_dialog(qtbot, services, event_bus)

    qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    assert not dialog.isVisible()
    assert answer == [False]


def test_with_changes_it_asks_and_can_keep_editing(qtbot, services, event_bus, answer):
    dialog = shown_dialog(qtbot, services, event_bus)
    dialog.name_input.setText("Viaje")

    dialog.reject()

    assert answer[1:] == [("¿Descartar los cambios?", "Descartar", "Seguir editando")]
    assert dialog.isVisible()
    assert dialog.name_input.text() == "Viaje"

    answer[0] = True
    dialog.reject()
    assert not dialog.isVisible()


def test_the_close_button_asks_too(qtbot, services, event_bus, answer):
    dialog = shown_dialog(qtbot, services, event_bus)
    dialog.name_input.setText("Viaje")

    dialog.close()

    assert dialog.isVisible()
    assert len(answer) == 2


def test_what_the_dialog_fills_in_by_itself_is_no_change(qtbot, services, event_bus, answer):
    tag = services.tags.create("Viaje", "#e11d48")
    dialog = shown_dialog(qtbot, services, event_bus, tag)

    dialog.reject()

    assert not dialog.isVisible()
    assert answer == [False]


def test_a_field_put_back_is_no_change(qtbot, services, event_bus, answer):
    tag = services.tags.create("Viaje", "#e11d48")
    dialog = shown_dialog(qtbot, services, event_bus, tag)
    dialog.name_input.setText("Vacaciones")
    dialog.name_input.setText("Viaje")

    dialog.reject()

    assert answer == [False]


def test_another_color_is_a_change(qtbot, services, event_bus, answer):
    dialog = shown_dialog(qtbot, services, event_bus)
    dialog.color_input.set_color("#123456")

    dialog.reject()

    assert len(answer) == 2


def test_saving_does_not_ask(qtbot, services, event_bus, answer):
    dialog = shown_dialog(qtbot, services, event_bus)
    dialog.name_input.setText("Viaje")

    dialog.save_button.click()

    assert services.tags.find("Viaje") is not None
    assert answer == [False]
