"""Field for the tags of a movement: chips for the chosen ones and a box to add more."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QToolButton, QVBoxLayout, QWidget

from nodus.models.payee import normalize_name
from nodus.services.tag_service import TagService
from nodus.ui.theme.design import Space
from nodus.ui.widgets.color import color_icon
from nodus.ui.widgets.name_completer import NameCompleter

# Color of the chip of a tag that does not exist yet and is created on saving.
NEW_TAG_COLOR = "#95a5a6"


def new_names_hint(names: list[str]) -> str:
    """ "Se creará «Viaje»", or "Se crearán «Viaje» y «Mudanza»"."""
    if not names:
        return ""
    quoted = [f"«{name}»" for name in names]
    if len(quoted) == 1:
        return f"Se creará {quoted[0]}"
    return f"Se crearán {', '.join(quoted[:-1])} y {quoted[-1]}"


class TagInput(QWidget):
    """Type a tag and press Enter or a comma to add it, choosing from the suggestions or
    writing a new name, which is created on saving. Each tag shows as a chip with its
    color; clicking a chip, or Backspace in the empty box, removes it. ``names`` also
    includes what is still typed in the box, so it is not lost on saving.
    """

    changed = Signal()

    def __init__(self, tags: TagService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tags = tags
        self._names: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.XS)
        self.chips = QWidget()
        self._chips_layout = QHBoxLayout(self.chips)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(Space.XS)
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Opcional · Enter para agregar")
        self.names_completer = NameCompleter(
            self.line_edit,
            lambda text: [t.name for t in tags.matches(text) if not self._has(t.name)],
        )
        self.hint = QLabel()
        self.hint.setObjectName("FieldHint")
        layout.addWidget(self.chips)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.hint)

        self.line_edit.installEventFilter(self)
        self.line_edit.textEdited.connect(self._split_on_comma)
        self.names_completer.activated.connect(self._add_from_completer)
        self._rebuild()

    def names(self) -> tuple[str, ...]:
        pending = self.line_edit.text().strip()
        extra = [pending] if normalize_name(pending) and not self._has(pending) else []
        return tuple(self._names + extra)

    def set_names(self, names: list[str]) -> None:
        self._names = list(names)
        self.line_edit.clear()
        self._rebuild()

    def add(self, name: str) -> None:
        """Adds a chip for ``name``, with an existing tag's own spelling."""
        name = name.strip()
        if normalize_name(name) and not self._has(name):
            tag = self._tags.find(name)
            self._names.append(tag.name if tag else name)
            self._rebuild()
        self.line_edit.clear()

    def remove(self, name: str) -> None:
        self._names.remove(name)
        self._rebuild()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Enter adds the typed tag instead of saving the dialog; Backspace in the empty
        box removes the last chip."""
        if watched is self.line_edit and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            text = self.line_edit.text()
            popup_open = self.names_completer.completer.popup().isVisible()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and text.strip() and not popup_open:
                self.add(text)
                return True
            if key == Qt.Key.Key_Backspace and not text and self._names:
                self.remove(self._names[-1])
                return True
        return super().eventFilter(watched, event)

    def _has(self, name: str) -> bool:
        wanted = normalize_name(name)
        return any(normalize_name(existing) == wanted for existing in self._names)

    def _split_on_comma(self, text: str) -> None:
        if "," in text:
            *done, rest = text.split(",")
            for name in done:
                self.add(name)
            self.line_edit.setText(rest.lstrip())

    def _add_from_completer(self, name: str) -> None:
        self.add(name)

    def _rebuild(self) -> None:
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        new = []
        for name in self._names:
            tag = self._tags.find(name)
            if tag is None:
                new.append(name)
            chip = QToolButton()
            chip.setObjectName("TagChip")
            chip.setText(f"{name}  ✕")
            chip.setIcon(color_icon(tag.color if tag else NEW_TAG_COLOR, 10))
            chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            chip.setToolTip("Quitar")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _checked=False, n=name: self.remove(n))
            self._chips_layout.addWidget(chip)
        self._chips_layout.addStretch()
        self.chips.setVisible(bool(self._names))
        self.hint.setText(new_names_hint(new))
        self.hint.setVisible(bool(new))
        self.changed.emit()
