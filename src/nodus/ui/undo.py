"""«Deshacer» in a toast, right after an action that changed data on one click."""

from __future__ import annotations

from PySide6.QtCore import SignalInstance
from PySide6.QtWidgets import QWidget

from nodus.services.app.undo_service import UndoRecord
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.ui.widgets.toast import show_toast, toast_host

UNDO_TEXT = "Deshacer"
UNDONE_TEXT = "Se deshizo."


def offer_undo(widget: QWidget, services: Services, *signals: SignalInstance) -> None:
    """Tells what the action just done did, with «Deshacer». Undoing announces
    ``signals`` again, the same ones the action announced, so every page refreshes."""
    record = services.undo.last
    host = toast_host(widget)  # the window: ``widget`` may be gone when «Deshacer» comes
    if record is not None and host is not None:
        show_toast(
            host, record.description, UNDO_TEXT, lambda: undo(host, services, record, *signals)
        )


def undo(
    widget: QWidget, services: Services, record: UndoRecord | None, *signals: SignalInstance
) -> None:
    """Undoes ``record`` (the last action when None) and says how it went."""
    try:
        services.undo.undo(record)
    except ValidationError as error:  # UndoError: what changed since, said for the user
        show_toast(widget, str(error))
        return
    for signal in signals:
        signal.emit()
    show_toast(widget, UNDONE_TEXT)
