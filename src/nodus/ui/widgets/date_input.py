"""Date field with a calendar, shared by every form that asks for a day."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, QEvent, QObject, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QFont, QMouseEvent, QPainter, QPalette, QShowEvent, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDateEdit,
    QStyle,
    QStyleOptionComboBox,
    QTableView,
    QWidget,
)

from nodus.ui.theme.design import Popup, TextRole, role_font

# The calendar grid: a row of day names over six weeks, seven days wide.
GRID_ROWS, GRID_COLUMNS = 7, 7


class Calendar(QCalendarWidget):
    """The month that opens under a date field, drawn like the lists that open over a
    page: square cells of ``Popup.CALENDAR_CELL``, the frame's ``Popup.PADDING``, and the
    chosen day like a list's chosen option. Days of the next and previous months are
    muted, so the month reads at a glance; today is in bold.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setGridVisible(False)
        # Without it Qt skips the stylesheet's frame on a plain widget like this one.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        padding = Popup.PADDING
        self.layout().setContentsMargins(padding, padding, padding, padding)
        self.grid = self.findChild(QTableView, "qt_calendar_calendarview")
        cell = Popup.CALENDAR_CELL
        self.grid.setMinimumSize(GRID_COLUMNS * cell, GRID_ROWS * cell)
        # Qt paints weekends in a fixed red that is hard to read on the dark theme; an
        # empty format makes them use the theme's text color like any other day.
        for weekend_day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.setWeekdayTextFormat(weekend_day, QTextCharFormat())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Room for the cells: Qt sizes the calendar from its font alone, and the window
        it opens in takes this size (Qt's ``sizeHint`` returns this one too)."""
        return super().minimumSizeHint().expandedTo(self.layout().minimumSize())

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Day names as captions, in the muted color of the theme shown now."""
        names = QTextCharFormat()
        names.setFont(role_font(TextRole.LABEL))
        names.setFontCapitalization(QFont.Capitalization.AllUppercase)
        names.setForeground(self.palette().color(QPalette.ColorRole.PlaceholderText))
        self.setHeaderTextFormat(names)
        super().showEvent(event)

    def paintCell(self, painter: QPainter, rect: QRect, day: QDate) -> None:  # noqa: N802
        # The grid's selection colors are the stylesheet's, the same as a list's.
        grid = self.grid.palette()
        chosen = day == self.selectedDate()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if chosen:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grid.color(QPalette.ColorRole.Highlight))
            inset = Popup.CALENDAR_CELL_GAP
            radius = Popup.ITEM_RADIUS
            painter.drawRoundedRect(
                QRectF(rect).adjusted(inset, inset, -inset, -inset), radius, radius
            )
        if chosen:
            color = grid.color(QPalette.ColorRole.HighlightedText)
        elif day.month() != self.monthShown():
            color = grid.color(QPalette.ColorRole.PlaceholderText)
        else:
            color = grid.color(QPalette.ColorRole.Text)
        painter.setPen(color)
        font = QFont(self.font())
        if day == QDate.currentDate():
            font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(day.day()))
        painter.restore()


class DateInput(QDateEdit):
    """A dd/mm/yyyy field that opens a calendar, starting on today.

    A click anywhere on the field opens the calendar, as a click on a list opens it. Qt
    opens it only from the arrow: the text is a line edit of its own, on top of the
    field, that takes the click and shows a text cursor. The date can still be typed
    after reaching the field with Tab.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setCalendarWidget(Calendar(self))
        self.setDisplayFormat("dd/MM/yyyy")
        self.set_day(date.today())
        self.lineEdit().installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """A press on the text opens the calendar instead of placing a cursor."""
        if (
            watched is self.lineEdit()
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.open_calendar()
            return True
        return super().eventFilter(watched, event)

    def open_calendar(self) -> None:
        """Opens the calendar the way Qt does for a press on the arrow."""
        arrow = QPointF(self._arrow_rect().center())
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            arrow,
            QPointF(self.mapToGlobal(arrow.toPoint())),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.mousePressEvent(press)

    def _arrow_rect(self) -> QRect:
        option = QStyleOptionComboBox()
        option.initFrom(self)
        option.editable = True
        option.subControls = QStyle.SubControl.SC_All
        return self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxArrow, self
        )

    def day(self) -> date:
        return self.date().toPython()

    def set_day(self, day: date) -> None:
        self.setDate(QDate(day.year, day.month, day.day))
