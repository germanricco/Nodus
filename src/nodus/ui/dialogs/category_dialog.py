"""Dialog to create or edit a category."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.models.category import Category
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES, TYPE_NAME, FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import TRANSACTION_TYPE_LABELS
from nodus.ui.widgets.color import ColorPicker
from nodus.ui.widgets.combo_box import ComboBox

NO_PARENT_LABEL = "Ninguna (categoría principal)"


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
            action = SAVE_CHANGES
        else:
            action = "Agregar subcategoría" if parent_id else "Agregar categoría"
        super().__init__("Editar categoría" if category else "Nueva categoría", parent, action)
        self._services = services
        self._event_bus = event_bus
        self._category = category

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej.: Mascotas, Gimnasio, Alquiler")
        self.kind_input = ComboBox()
        for transaction_type, label in TRANSACTION_TYPE_LABELS.items():
            self.kind_input.addItem(label, transaction_type)
        self.parent_input = ComboBox()
        self.color_input = ColorPicker()

        self.form.addRow("Nombre", self.name_input)
        self.form.addRow("Tipo", self.kind_input)
        self.form.addRow("Dentro de", self.parent_input)
        self.form.addRow("Color", self.color_input)
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
        self.parent_input.addItem(NO_PARENT_LABEL, None)
        for node in self._services.categories.category_tree(self.kind_input.currentData()):
            if not node.category.is_system:
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
        return self.required((self.name_input, TYPE_NAME))

    def save(self) -> None:
        name = self.name_input.text()
        color = self.color_input.color()
        if self._category:
            self._services.categories.update(self._category.id, name, color)
        else:
            self._services.categories.create(
                name, self.kind_input.currentData(), color, self.parent_input.currentData()
            )
        self._event_bus.categories_changed.emit()
