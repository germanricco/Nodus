"""A quiet line that leads to related pages: "Aporta a: Vacaciones, Auto"."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from nodus.ui.theme.design import Space
from nodus.ui.widgets.style import clear_layout, muted_label


@dataclass(frozen=True)
class Link:
    """One item of the line: its text, what its tooltip says and what a click opens."""

    text: str
    tooltip: str
    open: Callable[[], object]


class LinkLine(QWidget):
    """A gray label followed by links, each to another page, under a page's figures; it
    hides while there is nothing to link to."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Space.S)
        self.links: list[QPushButton] = []

    def set_links(self, label: str, links: list[Link]) -> None:
        clear_layout(self._layout)
        self.links = []
        self.setHidden(not links)
        if not links:
            return
        self._layout.addWidget(muted_label(label))
        for link in links:
            button = QPushButton(link.text)
            button.setObjectName("LinkButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(link.tooltip)
            button.clicked.connect(lambda _checked=False, go=link.open: go())
            self._layout.addWidget(button)
            self.links.append(button)
        self._layout.addStretch()
