"""The dialog that picks any range of days for the period selector."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.models.period import Period
from nodus.services.errors import ValidationError
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.widgets.date_input import DateInput


class DateRangeDialog(FormDialog):
    """Asks for a first and a last day, starting on ``period``. After it is accepted,
    ``period`` holds the chosen range."""

    def __init__(self, period: Period, parent: QWidget | None = None) -> None:
        super().__init__("Elegir fechas", parent, "Aplicar")
        self.period = period
        self.start_input = DateInput()
        self.start_input.set_day(period.start)
        self.end_input = DateInput()
        self.end_input.set_day(period.end)
        self.form.addRow("Desde", self.start_input)
        self.form.addRow("Hasta", self.end_input)

    def save(self) -> None:
        start, end = self.start_input.day(), self.end_input.day()
        if end < start:
            raise ValidationError("«Desde» no puede ser posterior a «Hasta».")
        self.period = Period(start, end)
