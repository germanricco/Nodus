"""Dialogs to create, edit and merge payees."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QWidget

from nodus.models.payee import Payee
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.widgets.selectors import CategoryComboBox

NO_DEFAULT_CATEGORY = "Sin categoría predeterminada"


class PayeeDialog(FormDialog):
    """Creates a payee, or renames ``payee`` and changes its default category.

    The default category fills in the category of new transactions with this payee, so
    both expense and income categories are offered.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        payee: Payee | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Editar beneficiario" if payee else "Nuevo beneficiario", parent)
        self._services = services
        self._event_bus = event_bus
        self._payee = payee

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej.: Coto, Edenor, Mercado Libre")
        self.category_input = CategoryComboBox()
        categories = services.categories
        self.category_input.set_categories(
            [
                ("Gastos", categories.category_tree(TransactionType.EXPENSE)),
                ("Ingresos", categories.category_tree(TransactionType.INCOME)),
            ],
            NO_DEFAULT_CATEGORY,
        )
        hint = QLabel("Se completa sola al elegir este beneficiario en un movimiento.")
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)

        self.form.addRow("Nombre", self.name_input)
        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("", hint)

        if payee:
            self.name_input.setText(payee.name)
            self.category_input.select(payee.default_category_id)

    def save(self) -> None:
        name = self.name_input.text()
        category_id = self.category_input.current_id()
        if self._payee:
            self._services.payees.update(self._payee.id, name, category_id)
        else:
            self._services.payees.create(name, category_id)
        self._event_bus.payees_changed.emit()


class MergePayeeDialog(FormDialog):
    """Moves the transactions of ``payee`` to another payee and deletes it, for duplicates
    such as "Coto" and "Coto Online"."""

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        payee: Payee,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"Unir «{payee.name}» con…", parent)
        self._services = services
        self._event_bus = event_bus
        self._payee = payee
        self._count = services.payees.transaction_count(payee.id)

        self.target_input = QComboBox()
        for other in services.payees.list_payees():
            if other.id != payee.id:
                self.target_input.addItem(other.name, other.id)
        self.result_label = QLabel()
        self.result_label.setObjectName("FieldHint")
        self.result_label.setWordWrap(True)
        self.form.addRow("Beneficiario", self.target_input)
        self.form.addRow("", self.result_label)
        self.save_button.setText("Unir")

        self.target_input.currentIndexChanged.connect(self._update_result)
        self._update_result()

    def _update_result(self) -> None:
        target, name = self.target_input.currentText(), self._payee.name
        if self._count == 0:
            text = f"«{name}» no tiene movimientos y se elimina."
        elif self._count == 1:
            text = f"Su movimiento pasa a «{target}» y «{name}» se elimina."
        else:
            text = f"Sus {self._count} movimientos pasan a «{target}» y «{name}» se elimina."
        self.result_label.setText(text)

    def save(self) -> None:
        self._services.payees.merge(self._payee.id, self.target_input.currentData())
        self._event_bus.payees_changed.emit()
        self._event_bus.transactions_changed.emit()
