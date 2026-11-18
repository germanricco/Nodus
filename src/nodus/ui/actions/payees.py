"""Deleting payees, from the list in Beneficiarios or from a payee's page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.i18n import _, ngettext
from nodus.services.classification.payee_service import PayeeSummary
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.event_bus import EventBus


def payee_delete_warning(summaries: list[PayeeSummary]) -> str:
    """What deleting payees does: their movements stay, without a payee."""
    if len(summaries) == 1:
        text = _("Se va a eliminar «{name}».").format(name=summaries[0].payee.name)
    else:
        text = _("Se van a eliminar {count} beneficiarios.").format(count=len(summaries))
    count = sum(summary.count for summary in summaries)
    if count:
        text += " " + ngettext(
            "{count} movimiento queda sin beneficiario.",
            "{count} movimientos quedan sin beneficiario.",
            count,
        ).format(count=count)
    return text


def delete_payees(
    parent: QWidget, services: Services, event_bus: EventBus, summaries: list[PayeeSummary]
) -> bool:
    """Deletes the payees of ``summaries`` once the user confirms."""
    return delete_with_confirm(
        parent,
        ngettext("Eliminar beneficiario", "Eliminar {count} beneficiarios", len(summaries)).format(
            count=len(summaries)
        ),
        payee_delete_warning(summaries),
        lambda: services.payees.delete_many([summary.payee.id for summary in summaries]),
        event_bus.payees_changed,
        event_bus.transactions_changed,
    )
