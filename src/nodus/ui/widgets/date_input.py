"""Date field with a calendar, shared by every form that asks for a day."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import QDateEdit, QWidget


class DateInput(QDateEdit):
    """A dd/mm/yyyy field that opens a calendar, starting on today."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd/MM/yyyy")
        # Qt paints weekends in a fixed red that is hard to read on the dark theme; an
        # empty format makes them use the theme's text color like any other day.
        for weekend_day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.calendarWidget().setWeekdayTextFormat(weekend_day, QTextCharFormat())
        self.set_day(date.today())

    def day(self) -> date:
        return self.date().toPython()

    def set_day(self, day: date) -> None:
        self.setDate(QDate(day.year, day.month, day.day))
