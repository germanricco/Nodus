"""Deleting tags, from the list in Etiquetas or from a tag's page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.services.classification.tag_service import TagSummary
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.tag_dialogs import announce_tag_change
from nodus.ui.event_bus import EventBus
from nodus.ui.text.labels import movements_text


def tag_delete_warning(services: Services, summaries: list[TagSummary]) -> str:
    """What deleting tags does: their movements lose them but stay."""
    if len(summaries) == 1:
        text = f"Se va a eliminar «{summaries[0].tag.name}»."
        count = summaries[0].count
    else:
        text = f"Se van a eliminar {len(summaries)} etiquetas."
        count = services.tags.tagged_count([summary.tag.id for summary in summaries])
    if count:
        lose = "la pierden" if len(summaries) == 1 else "pierden alguna"
        text += f" {movements_text(count)} {lose}; los movimientos no se borran."
    return text


def delete_tags(
    parent: QWidget, services: Services, event_bus: EventBus, summaries: list[TagSummary]
) -> bool:
    """Deletes the tags of ``summaries`` once the user confirms."""
    title = "Eliminar etiqueta" if len(summaries) == 1 else f"Eliminar {len(summaries)} etiquetas"
    if not confirm(parent, title, tag_delete_warning(services, summaries)):
        return False
    services.tags.delete_many([summary.tag.id for summary in summaries])
    announce_tag_change(event_bus)
    return True
