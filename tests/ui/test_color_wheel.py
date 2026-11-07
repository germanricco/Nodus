"""The color wheel popup and the «+» swatch that opens it."""

import pytest
from PySide6.QtCore import QPointF

from nodus.models.palette import PALETTE
from nodus.ui.widgets.color import ColorPicker
from nodus.ui.widgets.color_wheel import VALUE_STEPS, ColorWheelPopup


@pytest.fixture
def picker(qtbot) -> ColorPicker:
    widget = ColorPicker()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_the_wheel_swatch_comes_after_the_last_color(picker):
    def position(widget):
        row, column, _rows, _columns = picker._grid.getItemPosition(picker._grid.indexOf(widget))
        return row * ColorPicker.COLUMNS + column

    assert position(picker.wheel_swatch) == len(PALETTE)

    picker.set_color("#123456")

    assert position(picker.wheel_swatch) == len(PALETTE) + 1


def test_a_color_chosen_on_the_wheel_becomes_the_picker_color(qtbot, picker):
    picker.wheel_swatch.click()
    popup = picker.wheel_popup
    assert popup.isVisible()
    assert popup.hex_input.text() == PALETTE[0]

    popup.hex_input.textEdited.emit("#0a7f5c")
    popup.accept_button.click()

    assert picker.color() == "#0a7f5c"
    assert not popup.isVisible()


def test_cancelling_keeps_the_color(qtbot, picker):
    picker.set_color(PALETTE[3])
    picker.open_wheel()

    picker.wheel_popup.set_color("#000000")
    picker.wheel_popup.close()

    assert picker.color() == PALETTE[3]


@pytest.fixture
def popup(qtbot) -> ColorWheelPopup:
    widget = ColorWheelPopup("#ff0000")
    qtbot.addWidget(widget)
    return widget


def test_the_center_of_the_wheel_is_white(popup):
    popup.wheel.pick(QPointF(popup.wheel.width() / 2, popup.wheel.height() / 2))

    assert popup.color() == "#ffffff"
    assert popup.hex_input.text() == "#ffffff"


def test_the_angle_is_the_hue(popup):
    wheel = popup.wheel
    top = QPointF(wheel.width() / 2, 2)  # a quarter turn counterclockwise from red

    wheel.pick(top)

    assert popup.color() == "#80ff00"


def test_brightness_darkens_the_color(popup):
    popup.value_slider.setValue(VALUE_STEPS // 2)

    assert popup.color() == "#800000"
    assert popup.hex_input.text() == "#800000"


def test_an_incomplete_code_cannot_be_used(popup):
    popup.hex_input.setText("#12")
    popup.hex_input.textEdited.emit("#12")

    assert not popup.accept_button.isEnabled()
    assert popup.color() == "#ff0000"

    popup.hex_input.textEdited.emit("123abc")

    assert popup.accept_button.isEnabled()
    assert popup.color() == "#123abc"
