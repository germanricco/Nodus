"""A button says it is working while what it started runs, and always comes back."""

import pytest
from PySide6.QtWidgets import QPushButton

from nodus.ui.background import BackgroundCall
from nodus.ui.widgets.busy import busy, is_busy, start_busy, stop_busy


@pytest.fixture
def button(qtbot) -> QPushButton:
    button = QPushButton("Hacer copia")
    qtbot.addWidget(button)
    return button


def test_busy_shows_it_while_it_runs(button):
    with busy(button, "Guardando…"):
        assert not button.isEnabled()
        assert button.text() == "Guardando…"

    assert button.isEnabled()
    assert button.text() == "Hacer copia"


def test_busy_gives_the_button_back_even_when_it_fails(button):
    with pytest.raises(OSError), busy(button, "Guardando…"):
        raise OSError("disco lleno")

    assert button.isEnabled()
    assert button.text() == "Hacer copia"


def test_starting_twice_keeps_the_first_text(button):
    start_busy(button, "Actualizando…")
    start_busy(button, "Actualizando…")
    assert is_busy(button)

    stop_busy(button)

    assert button.text() == "Hacer copia"
    assert not is_busy(button)


def test_a_background_call_that_fails_says_so(qtbot):
    def broken():
        raise OSError("sin conexión")

    call = BackgroundCall(broken)

    with qtbot.waitSignal(call.failed):
        call.start()
