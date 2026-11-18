"""Dialogs to create, edit and merge payees."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.i18n import N_, _, ngettext
from nodus.models.payee import Payee
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES, TYPE_NAME, FormDialog
from nodus.ui.dialogs.merge_dialog import MergeDialog, MergeItem
from nodus.ui.event_bus import EventBus
from nodus.ui.undo import offer_undo
from nodus.ui.widgets.inputs.selectors import CategoryComboBox
from nodus.ui.widgets.style import hint_label

NO_DEFAULT_CATEGORY = N_("Sin categoría predeterminada")


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
        super().__init__(
            _("Editar beneficiario") if payee else _("Nuevo beneficiario"),
            parent,
            _(SAVE_CHANGES) if payee else _("Agregar beneficiario"),
        )
        self._services = services
        self._event_bus = event_bus
        self._payee = payee

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(_("Ej.: Coto, Edenor, Mercado Libre"))
        self.category_input = CategoryComboBox()
        categories = services.categories
        self.category_input.set_categories(
            [
                (_("Gastos"), categories.category_tree(TransactionType.EXPENSE)),
                (_("Ingresos"), categories.category_tree(TransactionType.INCOME)),
            ],
            _(NO_DEFAULT_CATEGORY),
        )
        hint = hint_label(_("Se completa sola al elegir este beneficiario en un movimiento."))
        hint.setWordWrap(True)

        self.form.addRow(_("Nombre"), self.name_input)
        self.bind_field(self.name_input, "name")
        self.form.addRow(_("Categoría"), self.category_input)
        self.form.addRow("", hint)

        if payee:
            self.name_input.setText(payee.name)
            self.category_input.select(payee.default_category_id)

    def missing(self) -> dict[QWidget, str]:
        return self.required((self.name_input, _(TYPE_NAME)))

    def save(self) -> None:
        name = self.name_input.text()
        category_id = self.category_input.current_id()
        if self._payee:
            self._services.payees.update(self._payee.id, name, category_id)
        else:
            self._services.payees.create(name, category_id)
        self._event_bus.payees_changed.emit()


class MergePayeeDialog(MergeDialog):
    """Moves the transactions of ``payees`` to one payee and deletes the rest, for
    duplicates such as "Coto" and "Coto Online".

    One payee joins another of the list; several join the one the user keeps.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        payees: list[Payee],
        parent: QWidget | None = None,
    ) -> None:
        chosen = {payee.id for payee in payees}
        others = [(p.name, p.id) for p in services.payees.list_payees() if p.id not in chosen]
        sources = [
            MergeItem(payee.name, payee.id, services.payees.transaction_count(payee.id))
            for payee in payees
        ]
        several_title = ngettext(
            "Unir {count} beneficiario", "Unir {count} beneficiarios", len(payees)
        ).format(count=len(payees))
        super().__init__(sources, _("Beneficiario"), several_title, others, parent)
        self._services = services
        self._event_bus = event_bus

    def merge(self, source_ids: list[int], target_id: int) -> None:
        self._services.payees.merge_many(source_ids, target_id)
        bus = self._event_bus
        bus.payees_changed.emit()
        bus.transactions_changed.emit()
        offer_undo(self, self._services, bus.payees_changed, bus.transactions_changed)
