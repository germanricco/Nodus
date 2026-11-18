"""The date field: a click anywhere on it opens its calendar, the date can still be
typed, and the calendar takes its measures from the design scale (``Popup``)."""

from datetime import date

from factories import transaction_dialog
from menus import click_at
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDateTimeEdit

from nodus.models.period import FIRST_DAY, LAST_DAY
from nodus.ui.theme.design import Popup
from nodus.ui.widgets.inputs.date_input import Calendar, DateInput


def open_calendar(qtbot, field: DateInput) -> Calendar:
    click_at(field)
    calendar = field.calendarWidget()
    qtbot.waitUntil(calendar.isVisible)
    return calendar


def test_a_click_on_the_date_text_opens_the_calendar(qtbot, services, event_bus, pesos, theme):
    dialog = transaction_dialog(qtbot, services, event_bus, theme=theme, show=True)

    calendar = open_calendar(qtbot, dialog.date_input)

    assert calendar.isVisible()


def test_the_date_can_still_be_typed(qtbot, services, event_bus, pesos, theme):
    dialog = transaction_dialog(qtbot, services, event_bus, theme=theme, show=True)
    field = dialog.date_input
    field.setFocus()
    field.setSelectedSection(QDateTimeEdit.Section.YearSection)

    qtbot.keyClicks(field, "2025")

    assert field.day().year == 2025


def test_the_calendar_takes_the_popup_steps(qtbot, services, event_bus, pesos, theme):
    dialog = transaction_dialog(qtbot, services, event_bus, theme=theme, show=True)

    calendar = open_calendar(qtbot, dialog.date_input)

    grid = calendar.grid
    assert grid.height() >= 7 * Popup.CALENDAR_CELL  # day names and six weeks
    assert grid.width() >= 7 * Popup.CALENDAR_CELL
    assert calendar.layout().contentsMargins().top() == Popup.PADDING
    assert calendar.height() <= calendar.window().height()  # never cut off


def test_a_click_on_the_date_text_lands_on_its_line_edit(qtbot, services, event_bus, pesos, theme):
    """The text is a child line edit: that is where a real click goes, and it must open
    the calendar rather than place a cursor."""
    dialog = transaction_dialog(qtbot, services, event_bus, theme=theme, show=True)
    field = dialog.date_input

    assert field.childAt(field.rect().center()) is field.lineEdit()
    QTest.mouseClick(field.lineEdit(), Qt.MouseButton.LeftButton)

    qtbot.waitUntil(field.calendarWidget().isVisible)


def test_the_calendar_keeps_to_the_days_a_date_can_take(qtbot):
    """Past ``LAST_DAY`` the next charge or the last installment could not be computed."""
    field = DateInput()
    qtbot.addWidget(field)
    assert (field.minimumDate().toPython(), field.maximumDate().toPython()) == (FIRST_DAY, LAST_DAY)


def test_in_english_the_date_field_writes_the_month_first(qtbot, english):
    field = DateInput()
    qtbot.addWidget(field)
    field.set_day(date(2026, 11, 5))

    assert field.text() == "11/05/2026"
