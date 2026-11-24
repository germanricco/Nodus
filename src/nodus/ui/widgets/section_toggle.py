"""A section's title that folds what is under it, in small capitals with its arrow."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QWidget

from nodus.i18n import _


class SectionToggle(QPushButton):
    """«CUENTAS  ▾»: a click folds the section (▸) or unfolds it (▾). The owner shows or
    hides what is under it and saves the choice, so the title only says and asks."""

    fold_toggled = Signal(bool)  # folded

    def __init__(self, title: str, folded: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SectionToggle")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title = title
        self.set_folded(folded)
        self.clicked.connect(lambda: self.fold_toggled.emit(not self._folded))

    @property
    def folded(self) -> bool:
        return self._folded

    def set_title(self, title: str) -> None:
        self._title = title
        self.set_folded(self._folded)

    def set_folded(self, folded: bool) -> None:
        self._folded = folded
        self.setText(f"{self._title.upper()}  {'▸' if folded else '▾'}")
        hint = _("Mostrar") if folded else _("Ocultar")
        self.setToolTip(hint)
        self.setAccessibleName(f"{self._title}: {hint.lower()}")
