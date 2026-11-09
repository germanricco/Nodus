"""Text field for a payee, with suggestions from the existing ones."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from nodus.models.payee import normalize_name
from nodus.services.payee_service import PayeeService
from nodus.ui.theme.design import Space
from nodus.ui.widgets.name_completer import NameCompleter


class PayeeInput(QWidget):
    """Type a few letters and pick a payee, or type a new name that is created on saving.

    The suggestions ignore case and accents and also match in the middle of a name (see
    ``NameCompleter``). Under the field, a hint tells when a name is new. Emits ``payee_chosen``
    with the payee when the text names an existing one, so the form can fill in its
    category.
    """

    payee_chosen = Signal(object)

    def __init__(self, payees: PayeeService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payees = payees
        self._last_chosen_id: int | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.XXS)
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Opcional")
        self.names = NameCompleter(
            self.line_edit, lambda text: [p.name for p in payees.matches(text)]
        )
        self.completer = self.names.completer
        self.hint = QLabel()
        self.hint.setObjectName("FieldHint")
        self.hint.hide()
        layout.addWidget(self.line_edit)
        layout.addWidget(self.hint)

        self.line_edit.textChanged.connect(self._update_hint)
        self.names.activated.connect(self._choose)
        self.line_edit.editingFinished.connect(lambda: self._choose(self.text()))

    def text(self) -> str:
        return self.line_edit.text()

    def set_text(self, name: str) -> None:
        """Shows ``name`` without suggesting anything, as when editing a transaction."""
        self.line_edit.setText(name)
        payee = self._payees.find(name)
        self._last_chosen_id = payee.id if payee else None

    def _update_hint(self, text: str) -> None:
        name = text.strip()
        is_new = bool(normalize_name(name)) and self._payees.find(name) is None
        self.hint.setText(f"Se creará «{name}»" if is_new else "")
        self.hint.setVisible(is_new)

    def _choose(self, text: str) -> None:
        """Announces the payee ``text`` names, once per payee."""
        payee = self._payees.find(text)
        if payee is None:
            self._last_chosen_id = None
        elif payee.id != self._last_chosen_id:
            self._last_chosen_id = payee.id
            self.payee_chosen.emit(payee)
