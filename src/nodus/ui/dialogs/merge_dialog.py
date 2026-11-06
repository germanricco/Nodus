"""The dialog that merges a duplicate payee or tag into another one."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QWidget

from nodus.ui.dialogs.form_dialog import FormDialog


class MergeDialog(FormDialog):
    """Asks which item ``name`` joins and says what happens to its ``count`` movements.

    ``others`` are the candidates as (name, id). Subclasses carry out ``merge``.
    """

    def __init__(
        self,
        name: str,
        field_label: str,
        others: list[tuple[str, int]],
        count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"Unir «{name}» con…", parent)
        self._name = name
        self._count = count

        self.target_input = QComboBox()
        for other_name, other_id in others:
            self.target_input.addItem(other_name, other_id)
        self.result_label = QLabel()
        self.result_label.setObjectName("FieldHint")
        self.result_label.setWordWrap(True)
        self.form.addRow(field_label, self.target_input)
        self.form.addRow("", self.result_label)
        self.save_button.setText("Unir")

        self.target_input.currentIndexChanged.connect(self._update_result)
        self._update_result()

    def merge(self, target_id: int) -> None:
        raise NotImplementedError

    def save(self) -> None:
        self.merge(self.target_input.currentData())

    def _update_result(self) -> None:
        target, name = self.target_input.currentText(), self._name
        if self._count == 0:
            text = f"«{name}» no tiene movimientos y se elimina."
        elif self._count == 1:
            text = f"Su movimiento pasa a «{target}» y «{name}» se elimina."
        else:
            text = f"Sus {self._count} movimientos pasan a «{target}» y «{name}» se elimina."
        self.result_label.setText(text)
