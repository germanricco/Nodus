"""The dialog that edits several transactions at once."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from nodus.models.bulk_changes import BulkChanges
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import transactions_text
from nodus.ui.widgets.payee_input import PayeeInput
from nodus.ui.widgets.selectors import CategoryComboBox
from nodus.ui.widgets.tag_input import TagInput

UNCHANGED = "Sin cambios"
MIXED_KINDS_HINT = "La categoría cambia solo si todas son gastos o todas son ingresos."
TRANSFERS_HINT = "Las transferencias solo cambian su nota."


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
        super().__init__(f"Editar {count}", parent, f"Aplicar a {count}")
        self._services = services
        self._event_bus = event_bus
        self._ids = [t.id for t in transactions]
        movements = [t for t in transactions if not t.is_transfer]

        self.category_input = CategoryComboBox()
        kind = shared_kind(transactions)
        if kind is not None:
            self.category_input.set_categories(
                [(None, services.categories.category_tree(kind))], all_label=UNCHANGED
            )
        else:
            self.category_input.set_categories([], all_label=UNCHANGED)
            self.category_input.setEnabled(False)
            self.category_input.setToolTip(MIXED_KINDS_HINT if movements else TRANSFERS_HINT)
        self.payee_input = PayeeInput(services.payees)
        self.payee_input.line_edit.setPlaceholderText(UNCHANGED)
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText(UNCHANGED)
        self.add_tags_input = TagInput(services.tags)
        self.remove_tags_input = TagInput(services.tags)
        for tags_input in (self.add_tags_input, self.remove_tags_input):
            tags_input.line_edit.setPlaceholderText("Ninguna · Enter para agregar")
        for widget in (self.payee_input, self.add_tags_input, self.remove_tags_input):
            widget.setEnabled(bool(movements))

        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("Beneficiario", self.payee_input)
        self.form.addRow("Nota", self.note_input)
        self.form.addRow("Agregar etiquetas", self.add_tags_input)
        self.form.addRow("Quitar etiquetas", self.remove_tags_input)
        hint = QLabel(self._hint(transactions, kind))
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)
        self.form.addRow("", hint)

    @staticmethod
    def _hint(transactions: list[Transaction], kind: TransactionType | None) -> str:
        sentences = ["Solo cambia lo que completes."]
        if any(t.is_transfer for t in transactions):
            sentences.append(TRANSFERS_HINT)
        elif kind is None:
            sentences.append(MIXED_KINDS_HINT)
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
        creates_tags = any(self._services.tags.find(name) is None for name in changes.add_tags)
        self._services.transactions.bulk_edit(self._ids, changes)
        self._event_bus.transactions_changed.emit()
        if changes.payee_name.strip():
            self._event_bus.payees_changed.emit()
        if creates_tags:
            self._event_bus.tags_changed.emit()
