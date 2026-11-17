"""Deleting payees, from the list in Beneficiarios or from a payee's page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.services.classification.payee_service import PayeeSummary
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.event_bus import EventBus
from nodus.ui.text.labels import movements_text


def payee_delete_warning(summaries: list[PayeeSummary]) -> str:
    """What deleting payees does: their movements stay, without a payee."""
    if len(summaries) == 1:
        text = f"Se va a eliminar «{summaries[0].payee.name}»."
    else:
        text = f"Se van a eliminar {len(summaries)} beneficiarios."
    count = sum(summary.count for summary in summaries)
    if count:
        left = "queda" if count == 1 else "quedan"
        text += f" {movements_text(count)} {left} sin beneficiario."
    return text


def delete_payees(
    parent: QWidget, services: Services, event_bus: EventBus, summaries: list[PayeeSummary]
) -> bool:
    """Deletes the payees of ``summaries`` once the user confirms."""
    title = (
        "Eliminar beneficiario"
        if len(summaries) == 1
        else f"Eliminar {len(summaries)} beneficiarios"
    )
    if not confirm(parent, title, payee_delete_warning(summaries)):
        return False
    services.payees.delete_many([summary.payee.id for summary in summaries])
    event_bus.payees_changed.emit()
    event_bus.transactions_changed.emit()
    return True
