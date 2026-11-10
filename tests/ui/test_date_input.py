"""The date field: a click anywhere on it opens its calendar, the date can still be
typed, and the calendar takes its measures from the design scale (``Popup``)."""

import pytest
from menus import click_at
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDateTimeEdit

from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.theme.design import Popup
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.date_input import Calendar, DateInput


@pytest.fixture(params=[ThemeMode.LIGHT, ThemeMode.DARK], ids=["light", "dark"])
def theme(request, qapp) -> ThemeManager:
    return ThemeManager(qapp, request.param)


def make_dialog(qtbot, services, event_bus, theme) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, theme)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def open_calendar(qtbot, field: DateInput) -> Calendar:
    click_at(field)
    calendar = field.calendarWidget()
    qtbot.waitUntil(calendar.isVisible)
    return calendar


def test_a_click_on_the_date_text_opens_the_calendar(qtbot, services, event_bus, pesos, theme):
    dialog = make_dialog(qtbot, services, event_bus, theme)

    calendar = open_calendar(qtbot, dialog.date_input)

    assert calendar.isVisible()


def test_the_date_can_still_be_typed(qtbot, services, event_bus, pesos, theme):
    dialog = make_dialog(qtbot, services, event_bus, theme)
    field = dialog.date_input
    field.setFocus()
    field.setSelectedSection(QDateTimeEdit.Section.YearSection)

    qtbot.keyClicks(field, "2025")

    assert field.day().year == 2025


def test_the_calendar_takes_the_popup_steps(qtbot, services, event_bus, pesos, theme):
    dialog = make_dialog(qtbot, services, event_bus, theme)

    calendar = open_calendar(qtbot, dialog.date_input)

    grid = calendar.grid
    assert grid.height() >= 7 * Popup.CALENDAR_CELL  # day names and six weeks
    assert grid.width() >= 7 * Popup.CALENDAR_CELL
    assert calendar.layout().contentsMargins().top() == Popup.PADDING
    assert calendar.height() <= calendar.window().height()  # never cut off


def test_a_click_on_the_date_text_lands_on_its_line_edit(qtbot, services, event_bus, pesos, theme):
    """The text is a child line edit: that is where a real click goes, and it must open
    the calendar rather than place a cursor."""
    dialog = make_dialog(qtbot, services, event_bus, theme)
    field = dialog.date_input

    assert field.childAt(field.rect().center()) is field.lineEdit()
    QTest.mouseClick(field.lineEdit(), Qt.MouseButton.LeftButton)

    qtbot.waitUntil(field.calendarWidget().isVisible)
