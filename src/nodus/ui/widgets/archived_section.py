"""The archived items of a page, apart under a title that folds them away."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from nodus.i18n import _
from nodus.ui.theme.design import Space
from nodus.ui.widgets.section_toggle import SectionToggle


class ArchivedSection(QWidget):
    """«ARCHIVADAS (n) ▾» over ``content``, the archived accounts or goals: the same on
    every page that archives something. They are kept but no longer followed, so a click
    on the title folds them, to keep the page clean, and the page saves the choice
    (``fold_toggled``)."""

    def __init__(self, count: int, content: QWidget, folded: bool) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        self.toggle = SectionToggle(_("Archivadas") + f" ({count})", folded)
        self.toggle.setProperty("flush", True)
        self.fold_toggled = self.toggle.fold_toggled
        self.toggle.fold_toggled.connect(self.set_folded)
        layout.addWidget(self.toggle)
        self.content = content
        layout.addWidget(content)
        content.setVisible(not folded)

    @property
    def folded(self) -> bool:
        return self.toggle.folded

    def set_folded(self, folded: bool) -> None:
        self.toggle.set_folded(folded)
        self.content.setVisible(not folded)
