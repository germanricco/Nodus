"""What a charge's row offers wherever it shows: «Ya lo vi» and «Omitir», and paying it."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QWidget

from nodus.models.recurring_charge import RecurringCharge
from nodus.services.container import Services
from nodus.ui.dialogs.recurring_charge_dialog import PayChargeDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.undo import offer_undo
from nodus.ui.widgets.tables.charge_row import reminder_day
from nodus.ui.widgets.toast import show_toast, toast_host


def toggle_seen(
    widget: QWidget, services: Services, event_bus: EventBus, charge: RecurringCharge
) -> None:
    """«Ya lo vi» on ``charge``, or «Volver a avisarme» when it is put off, told in a
    toast with the day its warning comes back."""
    today = date.today()
    if services.recurring.is_quiet(charge, today):
        services.recurring.remind_again(charge.id, today)
        text = f"Te volvemos a avisar de {charge.name}."
    else:
        day = services.recurring.mark_seen(charge.id, today)
        text = f"Te recordamos {charge.name} {reminder_day(day, today)}."
    host = toast_host(widget)  # the row that asked is rebuilt by the refresh
    event_bus.recurring_changed.emit()
    if host is not None:
        show_toast(host, text)


def skip_charge(
    widget: QWidget, services: Services, event_bus: EventBus, charge: RecurringCharge
) -> None:
    """Moves ``charge`` to its next due date without recording a payment, with
    «Deshacer» in a toast."""
    services.recurring.skip(charge.id)
    event_bus.recurring_changed.emit()
    offer_undo(widget, services, event_bus.recurring_changed)


def pay_charge(
    parent: QWidget, services: Services, event_bus: EventBus, charge: RecurringCharge
) -> None:
    """Opens the form that records a payment of ``charge``."""
    PayChargeDialog(services, event_bus, charge, parent=parent.window()).exec()
