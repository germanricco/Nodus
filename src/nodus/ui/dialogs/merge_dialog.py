"""The dialog that merges duplicate payees or tags into one."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget

from nodus.i18n import _, ngettext, quoted
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.widgets.inputs.combo_box import ComboBox
from nodus.ui.widgets.style import hint_label


@dataclass(frozen=True)
class MergeItem:
    """A payee or tag as the dialog shows it: its name, id and how many movements it has."""

    name: str
    id: int
    count: int


def quoted_names(names: list[str]) -> str:
    """ "«A»", "«A» y «B»", "«A», «B» y «C»"."""
    marked = [quoted(name) for name in names]
    if len(marked) == 1:
        return marked[0]
    return _("{names} y {last}").format(names=", ".join(marked[:-1]), last=marked[-1])


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
        several_title: str,
        others: list[tuple[str, int]],
        parent: QWidget | None = None,
    ) -> None:
        """``several_title`` is the title when merging several ("Unir 3 beneficiarios")."""
        single = len(sources) == 1
        title = _("Unir «{name}» con…").format(name=sources[0].name) if single else several_title
        super().__init__(title, parent, _("Unir"))
        self._sources = sources

        self.target_input = ComboBox()
        candidates = others if single else [(s.name, s.id) for s in sources]
        for name, item_id in candidates:
            self.target_input.addItem(name, item_id)
        self.result_label = hint_label()
        self.result_label.setWordWrap(True)
        self.form.addRow(field_label if single else _("Queda"), self.target_input)
        self.form.addRow("", self.result_label)

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
        if count == 0:
            text = ngettext(
                "{names} no tiene movimientos y se elimina.",
                "{names} no tienen movimientos y se eliminan.",
                len(leaving),
            )
        elif len(leaving) == 1:
            text = ngettext(
                "Su movimiento pasa a «{target}» y {names} se elimina.",
                "Sus {count} movimientos pasan a «{target}» y {names} se elimina.",
                count,
            )
        else:
            text = ngettext(
                "{count} movimiento pasa a «{target}» y se eliminan {names}.",
                "{count} movimientos pasan a «{target}» y se eliminan {names}.",
                count,
            )
        self.result_label.setText(text.format(names=names, target=target, count=count))
