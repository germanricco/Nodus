"""A recurring charge as a row: when it is due, its «Ya lo vi» and its quick «Pagar».
Inicio and the page of an account list them alike."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.models.recurring_charge import DueStatus, RecurringCharge
from nodus.ui.text.formatting import format_date
from nodus.ui.text.labels import due_label
from nodus.ui.theme.design import Space
from nodus.ui.widgets.change_badge import Tone, status_pill
from nodus.ui.widgets.pay_button import PayButton
from nodus.ui.widgets.style import RIGHT_ALIGNED, amount_label, muted_label
from nodus.ui.widgets.tables.row_actions import Effect, RowAction, install_row_actions

DUE_TONES = {
    DueStatus.OVERDUE: Tone.BAD,
    DueStatus.SOON: Tone.WARNING,
    DueStatus.LATER: Tone.NEUTRAL,
}
SEEN_TEXT = "Ya lo vi"
REMIND_AGAIN_TEXT = "Volver a avisarme"


def due_status_label(charge: RecurringCharge, today: date, quiet: bool) -> QLabel:
    """When the charge is due, in a pill: red once overdue, amber within the week, and
    gray again while the user has seen it (``RecurringChargeService.is_quiet``)."""
    tone = Tone.NEUTRAL if quiet else DUE_TONES[charge.status(today)]
    pill = status_pill(due_label(charge.days_until(today)), tone)
    if quiet:
        pill.setToolTip(
            f"Ya lo viste. Te lo recordamos {reminder_day(charge.quiet_until(), today)}."
        )
    return pill


def reminder_day(day: date, today: date) -> str:
    """When a warning put off comes back: «mañana» or «el 16/11/2026»."""
    return "mañana" if (day - today).days == 1 else f"el {format_date(day)}"


def seen_actions(
    charge: RecurringCharge, today: date, quiet: bool, toggled: SignalInstance
) -> list[RowAction]:
    """«Ya lo vi» while the charge warns with a day to spare, «Volver a avisarme» while
    it is seen (``quiet``); nothing otherwise (overdue, due tomorrow or not due soon)."""
    if quiet:
        text, icon = REMIND_AGAIN_TEXT, "bell"
    elif charge.can_be_seen(today):
        text, icon = SEEN_TEXT, "check"
    else:
        return []
    return [RowAction(text, lambda: toggled.emit(charge), icon, effect=Effect.TOGGLE)]


class UpcomingPaymentRow(QWidget):
    """A charge in the upcoming payments card: name, when it is due, amount and "Pagar".
    It answers as a row of Recurrentes: a double click pays it, a right click shows its
    menu."""

    pay_requested = Signal(object)  # RecurringCharge
    skip_requested = Signal(object)  # RecurringCharge
    seen_toggled = Signal(object)  # RecurringCharge

    def __init__(
        self, charge: RecurringCharge, today: date, quiet: bool, estimate: str = ""
    ) -> None:
        super().__init__()
        self.charge = charge
        self._today = today
        self._quiet = quiet
        install_row_actions(self, self.actions)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.XS, Space.S, Space.XS)
        layout.setSpacing(Space.S)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name = QLabel(charge.name)
        name.setObjectName("RowTitle")
        texts.addWidget(name)
        texts.addWidget(
            due_status_label(charge, today, quiet), alignment=Qt.AlignmentFlag.AlignLeft
        )
        layout.addLayout(texts, stretch=1)
        amounts = QVBoxLayout()
        amounts.setSpacing(0)
        amount = amount_label(charge.amount)
        amount.setObjectName("RowAmount")
        amounts.addWidget(amount)
        if estimate:  # on a line of its own, so the narrow card keeps its width
            estimate_label = muted_label(estimate)
            estimate_label.setAlignment(RIGHT_ALIGNED)
            amounts.addWidget(estimate_label)
        layout.addLayout(amounts)
        self.pay_button = PayButton()
        self.pay_button.clicked.connect(lambda: self.pay_requested.emit(charge))
        layout.addWidget(self.pay_button)

    def actions(self) -> list[RowAction]:
        """Paying and skipping, as in Recurrentes; the rest is in that page."""
        charge = self.charge
        return [
            RowAction(
                "Pagar",
                lambda: self.pay_requested.emit(charge),
                "pay",
                default=True,
                effect=Effect.OPEN,
            ),
            RowAction(
                "Omitir", lambda: self.skip_requested.emit(charge), "skip", effect=Effect.UNDOABLE
            ),
            *seen_actions(charge, self._today, self._quiet, self.seen_toggled),
        ]
