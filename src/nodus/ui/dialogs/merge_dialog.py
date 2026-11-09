"""The dialog that merges duplicate payees or tags into one."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QComboBox, QLabel, QWidget

from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.labels import movements_text


@dataclass(frozen=True)
class MergeItem:
    """A payee or tag as the dialog shows it: its name, id and how many movements it has."""

    name: str
    id: int
    count: int


def quoted_names(names: list[str]) -> str:
    """ "«A»", "«A» y «B»", "«A», «B» y «C»"."""
    quoted = [f"«{name}»" for name in names]
    return quoted[0] if len(quoted) == 1 else f"{', '.join(quoted[:-1])} y {quoted[-1]}"


class MergeDialog(FormDialog):
    """Asks which item the others join and says what happens to their movements.

    With one item in ``sources``, it joins one of ``others`` (name, id). With several,
    as when merging a selection, the user picks which of them stays. Subclasses carry
    out ``merge``.
    """

    def __init__(
        self,
        sources: list[MergeItem],
        field_label: str,
        plural_noun: str,
        others: list[tuple[str, int]],
        parent: QWidget | None = None,
    ) -> None:
        """``plural_noun`` names several items ("beneficiarios") in the title."""
        single = len(sources) == 1
        title = f"Unir «{sources[0].name}» con…" if single else f"Unir {len(sources)} {plural_noun}"
        super().__init__(title, parent)
        self._sources = sources

        self.target_input = QComboBox()
        candidates = others if single else [(s.name, s.id) for s in sources]
        for name, item_id in candidates:
            self.target_input.addItem(name, item_id)
        self.result_label = QLabel()
        self.result_label.setObjectName("FieldHint")
        self.result_label.setWordWrap(True)
        self.form.addRow(field_label if single else "Queda", self.target_input)
        self.form.addRow("", self.result_label)
        self.save_button.setText("Unir")

        self.target_input.currentIndexChanged.connect(self._update_result)
        self._update_result()

    def merge(self, source_ids: list[int], target_id: int) -> None:
        raise NotImplementedError

    def save(self) -> None:
        self.merge([source.id for source in self._sources], self.target_input.currentData())

    def _update_result(self) -> None:
        target_id, target = self.target_input.currentData(), self.target_input.currentText()
        leaving = [s for s in self._sources if s.id != target_id]
        names = quoted_names([s.name for s in leaving])
        count = sum(s.count for s in leaving)
        goes = "se elimina" if len(leaving) == 1 else "se eliminan"
        if count == 0:
            have = "no tiene" if len(leaving) == 1 else "no tienen"
            text = f"{names} {have} movimientos y {goes}."
        elif len(leaving) == 1 and count == 1:
            text = f"Su movimiento pasa a «{target}» y {names} {goes}."
        elif len(leaving) == 1:
            text = f"Sus {count} movimientos pasan a «{target}» y {names} {goes}."
        else:
            moves = "pasa" if count == 1 else "pasan"
            text = f"{movements_text(count)} {moves} a «{target}» y {goes} {names}."
        self.result_label.setText(text)
