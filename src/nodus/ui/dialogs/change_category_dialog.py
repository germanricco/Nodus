"""The dialog that moves several transactions to one category at once."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import transactions_text
from nodus.ui.widgets.selectors import CategoryComboBox


class ChangeCategoryDialog(FormDialog):
    """Asks for the category that ``transaction_ids``, all of ``kind``, move to."""

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        transaction_ids: list[int],
        kind: TransactionType,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Cambiar categoría", parent)
        self._services = services
        self._event_bus = event_bus
        self._transaction_ids = transaction_ids
        self.category_input = CategoryComboBox()
        self.category_input.set_categories([(None, services.categories.category_tree(kind))])
        hint = QLabel(f"{transactions_text(len(transaction_ids))} pasan a esta categoría.")
        hint.setObjectName("FieldHint")
        if len(transaction_ids) == 1:
            hint.setText("La transacción pasa a esta categoría.")
        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("", hint)
        self.save_button.setText("Cambiar")

    def save(self) -> None:
        self._services.transactions.set_category(
            self._transaction_ids, self.category_input.current_id()
        )
        self._event_bus.transactions_changed.emit()
