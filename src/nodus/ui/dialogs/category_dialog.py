"""Dialogs to create, edit and merge categories."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.i18n import N_, _
from nodus.models.category import Category
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.color_choice import color_picker, remember_color
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES, TYPE_NAME, FormDialog
from nodus.ui.dialogs.merge_dialog import MergeDialog, MergeItem
from nodus.ui.event_bus import EventBus
from nodus.ui.text.labels import TRANSACTION_TYPE_LABELS
from nodus.ui.widgets.inputs.combo_box import ComboBox

NO_PARENT_LABEL = N_("Ninguna (categoría principal)")


class CategoryDialog(FormDialog):
    """Creates a category, or renames and recolors ``category`` when given.

    Kind and parent are chosen only when creating: transactions already filed under a
    category depend on them, so they are locked while editing.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        category: Category | None = None,
        kind: TransactionType = TransactionType.EXPENSE,
        parent_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        if category:
            action = _(SAVE_CHANGES)
        else:
            action = _("Agregar subcategoría") if parent_id else _("Agregar categoría")
        super().__init__(
            _("Editar categoría") if category else _("Nueva categoría"), parent, action
        )
        self._services = services
        self._event_bus = event_bus
        self._category = category

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(_("Ej.: Mascotas, Gimnasio, Alquiler"))
        self.kind_input = ComboBox()
        for transaction_type, label in TRANSACTION_TYPE_LABELS.items():
            self.kind_input.addItem(_(label), transaction_type)
        self.parent_input = ComboBox()
        self.color_input = color_picker(services)

        self.form.addRow(_("Nombre"), self.name_input)
        self.form.addRow(_("Tipo"), self.kind_input)
        self.form.addRow(_("Dentro de"), self.parent_input)
        self.form.addRow(_("Color"), self.color_input)
        self.bind_field(self.name_input, "name")
        self.bind_field(self.parent_input, "parent_id")

        self.kind_input.currentIndexChanged.connect(self._fill_parents)
        if category:
            self._load(category)
        else:
            self.kind_input.setCurrentIndex(self.kind_input.findData(kind))
            self._fill_parents()
            self.parent_input.setCurrentIndex(self.parent_input.findData(parent_id))

    def _fill_parents(self) -> None:
        """Lists the categories that can hold a subcategory of the selected kind."""
        self.parent_input.clear()
        self.parent_input.addItem(_(NO_PARENT_LABEL), None)
        for node in self._services.categories.category_tree(self.kind_input.currentData()):
            if not node.category.is_fixed:
                self.parent_input.addItem(node.category.name, node.category.id)

    def _load(self, category: Category) -> None:
        self.name_input.setText(category.name)
        self.kind_input.setCurrentIndex(self.kind_input.findData(category.kind))
        self._fill_parents()
        self.parent_input.setCurrentIndex(self.parent_input.findData(category.parent_id))
        self.color_input.set_color(category.color)
        self.kind_input.setEnabled(False)
        self.parent_input.setEnabled(False)

    def missing(self) -> dict[QWidget, str]:
        return self.required((self.name_input, _(TYPE_NAME)))

    def save(self) -> None:
        name = self.name_input.text()
        color = self.color_input.color()
        if self._category:
            self._services.categories.update(self._category.id, name, color)
        else:
            self._services.categories.create(
                name, self.kind_input.currentData(), color, self.parent_input.currentData()
            )
        remember_color(self._services, color)
        self._event_bus.categories_changed.emit()


class MergeCategoryDialog(MergeDialog):
    """Moves the movements of ``category`` to another of its kind and deletes it, for
    duplicates such as «Comida» and «Supermercado». A copy of the data is made first, as
    when deleting."""

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        category: Category,
        parent: QWidget | None = None,
    ) -> None:
        categories = services.categories
        others = [(c.name, c.id) for c in categories.merge_targets(category.id)]
        source = MergeItem(category.name, category.id, categories.transaction_count(category.id))
        super().__init__([source], _("Categoría"), "", others, parent)
        self._services = services
        self._event_bus = event_bus

    def merge(self, source_ids: list[int], target_id: int) -> None:
        (source_id,) = source_ids
        self._services.categories.merge(source_id, target_id)
        bus = self._event_bus
        bus.categories_changed.emit()
        bus.transactions_changed.emit()
        bus.payees_changed.emit()
