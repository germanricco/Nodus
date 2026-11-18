"""Deleting tags, from the list in Etiquetas or from a tag's page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.i18n import _, ngettext
from nodus.services.classification.tag_service import TagSummary
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.dialogs.tag_dialogs import tag_changes
from nodus.ui.event_bus import EventBus


def tag_delete_warning(services: Services, summaries: list[TagSummary]) -> str:
    """What deleting tags does: their movements lose them but stay."""
    if len(summaries) == 1:
        text = _("Se va a eliminar «{name}».").format(name=summaries[0].tag.name)
        count = summaries[0].count
    else:
        text = _("Se van a eliminar {count} etiquetas.").format(count=len(summaries))
        count = services.tags.tagged_count([summary.tag.id for summary in summaries])
    if count:
        if len(summaries) == 1:
            lose = ngettext(
                "{count} movimiento la pierde; los movimientos no se borran.",
                "{count} movimientos la pierden; los movimientos no se borran.",
                count,
            )
        else:
            lose = ngettext(
                "{count} movimiento pierde alguna; los movimientos no se borran.",
                "{count} movimientos pierden alguna; los movimientos no se borran.",
                count,
            )
        text += " " + lose.format(count=count)
    return text


def delete_tags(
    parent: QWidget, services: Services, event_bus: EventBus, summaries: list[TagSummary]
) -> bool:
    """Deletes the tags of ``summaries`` once the user confirms."""
    return delete_with_confirm(
        parent,
        ngettext("Eliminar etiqueta", "Eliminar {count} etiquetas", len(summaries)).format(
            count=len(summaries)
        ),
        tag_delete_warning(services, summaries),
        lambda: services.tags.delete_many([summary.tag.id for summary in summaries]),
        *tag_changes(event_bus),
    )
