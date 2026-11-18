"""The dialog that edits several transactions at once."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.i18n import N_, _
from nodus.models.bulk_changes import BulkChanges
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.text.labels import transactions_text
from nodus.ui.undo import offer_undo
from nodus.ui.widgets.inputs.payee_input import PayeeInput
from nodus.ui.widgets.inputs.selectors import CategoryComboBox
from nodus.ui.widgets.inputs.tag_input import TagInput
from nodus.ui.widgets.style import hint_label

UNCHANGED = N_("Sin cambios")
MIXED_KINDS_HINT = N_("La categoría cambia solo si todas son gastos o todas son ingresos.")
TRANSFERS_HINT = N_("Las transferencias solo cambian su nota.")


def shared_kind(transactions: list[Transaction]) -> TransactionType | None:
    """The type the expenses and incomes among ``transactions`` share, which a new
    category must have; None when they mix or there are only transfers."""
    kinds = {t.type for t in transactions if not t.is_transfer}
    return kinds.pop() if len(kinds) == 1 else None


class BulkEditDialog(FormDialog):
    """Changes the category, payee, note or tags of ``transactions`` together.

    Every field starts as «Sin cambios», and only what the user fills in is applied, so
    fixing the payee of many movements leaves their notes as they were. Transfers have no
    category, payee or tags: they only take the note.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        transactions: list[Transaction],
        parent: QWidget | None = None,
    ) -> None:
        count = transactions_text(len(transactions))
        super().__init__(
            _("Editar {transactions}").format(transactions=count),
            parent,
            _("Aplicar a {transactions}").format(transactions=count),
        )
        self._services = services
        self._event_bus = event_bus
        self._ids = [t.id for t in transactions]
        movements = [t for t in transactions if not t.is_transfer]

        self.category_input = CategoryComboBox()
        kind = shared_kind(transactions)
        if kind is not None:
            self.category_input.set_categories(
                [(None, services.categories.category_tree(kind))], all_label=_(UNCHANGED)
            )
        else:
            self.category_input.set_categories([], all_label=_(UNCHANGED))
            self.category_input.setEnabled(False)
            self.category_input.setToolTip(_(MIXED_KINDS_HINT) if movements else _(TRANSFERS_HINT))
        self.payee_input = PayeeInput(services.payees)
        self.payee_input.line_edit.setPlaceholderText(_(UNCHANGED))
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText(_(UNCHANGED))
        self.add_tags_input = TagInput(services.tags)
        self.remove_tags_input = TagInput(services.tags)
        for tags_input in (self.add_tags_input, self.remove_tags_input):
            tags_input.line_edit.setPlaceholderText(_("Ninguna · Enter para agregar"))
        for widget in (self.payee_input, self.add_tags_input, self.remove_tags_input):
            widget.setEnabled(bool(movements))

        self.form.addRow(_("Categoría"), self.category_input)
        self.form.addRow(_("Beneficiario"), self.payee_input)
        self.form.addRow(_("Nota"), self.note_input)
        self.form.addRow(_("Agregar etiquetas"), self.add_tags_input)
        self.form.addRow(_("Quitar etiquetas"), self.remove_tags_input)
        hint = hint_label(self._hint(transactions, kind))
        hint.setWordWrap(True)
        self.form.addRow("", hint)

    @staticmethod
    def _hint(transactions: list[Transaction], kind: TransactionType | None) -> str:
        sentences = [_("Solo cambia lo que completes.")]
        if any(t.is_transfer for t in transactions):
            sentences.append(_(TRANSFERS_HINT))
        elif kind is None:
            sentences.append(_(MIXED_KINDS_HINT))
        return " ".join(sentences)

    def changes(self) -> BulkChanges:
        return BulkChanges(
            category_id=self.category_input.current_id(),
            payee_name=self.payee_input.text(),
            note=self.note_input.text(),
            add_tags=self.add_tags_input.names(),
            remove_tags=self.remove_tags_input.names(),
        )

    def save(self) -> None:
        changes = self.changes()
        creates_tags = self._services.tags.any_new(changes.add_tags)
        self._services.bulk_edits.apply(self._ids, changes)
        self._event_bus.transactions_changed.emit()
        if changes.payee_name.strip():
            self._event_bus.payees_changed.emit()
        if creates_tags:
            self._event_bus.tags_changed.emit()
        bus = self._event_bus
        # undoing may also delete the payee or tags it created, so every list refreshes
        offer_undo(
            self, self._services, bus.transactions_changed, bus.payees_changed, bus.tags_changed
        )
