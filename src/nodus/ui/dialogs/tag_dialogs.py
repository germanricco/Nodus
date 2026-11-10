"""Dialogs to create, edit and merge tags."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.models.palette import palette_color
from nodus.models.tag import Tag
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES, TYPE_NAME, FormDialog
from nodus.ui.dialogs.merge_dialog import MergeDialog, MergeItem
from nodus.ui.event_bus import EventBus
from nodus.ui.widgets.color import ColorPicker


def announce_tag_change(event_bus: EventBus) -> None:
    """Tags show in the transactions list too, so both get refreshed."""
    event_bus.tags_changed.emit()
    event_bus.transactions_changed.emit()


class TagDialog(FormDialog):
    """Creates a tag, or renames and recolors ``tag`` when given."""

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        tag: Tag | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Editar etiqueta" if tag else "Nueva etiqueta",
            parent,
            SAVE_CHANGES if tag else "Agregar etiqueta",
        )
        self._services = services
        self._event_bus = event_bus
        self._tag = tag

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej.: Vacaciones 2026, Trabajo, Mudanza")
        self.color_input = ColorPicker()
        self.form.addRow("Nombre", self.name_input)
        self.form.addRow("Color", self.color_input)
        self.bind_field(self.name_input, "name")

        if tag:
            self.name_input.setText(tag.name)
            self.color_input.set_color(tag.color)
        else:
            self.color_input.set_color(palette_color(len(services.tags.list_tags())))

    def missing(self) -> dict[QWidget, str]:
        return self.required((self.name_input, TYPE_NAME))

    def save(self) -> None:
        name, color = self.name_input.text(), self.color_input.color()
        if self._tag:
            self._services.tags.update(self._tag.id, name, color)
        else:
            self._services.tags.create(name, color)
        announce_tag_change(self._event_bus)


class MergeTagDialog(MergeDialog):
    """Gives one tag to the transactions of ``tags`` and deletes the rest, for duplicates
    such as "Viaje" and "Vacaciones".

    One tag joins another of the list; several join the one the user keeps.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        tags: list[Tag],
        parent: QWidget | None = None,
    ) -> None:
        chosen = {tag.id for tag in tags}
        others = [(t.name, t.id) for t in services.tags.list_tags() if t.id not in chosen]
        sources = [
            MergeItem(tag.name, tag.id, services.tags.transaction_count(tag.id)) for tag in tags
        ]
        super().__init__(sources, "Etiqueta", "etiquetas", others, parent)
        self._services = services
        self._event_bus = event_bus

    def merge(self, source_ids: list[int], target_id: int) -> None:
        self._services.tags.merge_many(source_ids, target_id)
        announce_tag_change(self._event_bus)
