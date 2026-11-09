"""The bar that takes the place of a page's header while several rows are chosen."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from nodus.ui.widgets.style import set_style_property


class SelectionBar(QFrame):
    """How many rows are chosen, an optional detail (such as what they add up to), the
    actions for all of them and «✕» to let them go."""

    cleared = Signal()

    def __init__(self, chosen_word: str = "seleccionadas") -> None:
        """``chosen_word`` agrees with what the rows are: "seleccionadas" (transacciones,
        etiquetas) or "seleccionados" (beneficiarios)."""
        super().__init__()
        self.setObjectName("SelectionBar")
        self._chosen_word = chosen_word
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 6, 4)
        layout.setSpacing(10)
        self.count_label = QLabel()
        self.count_label.setObjectName("RowTitle")
        self.detail_label = QLabel()
        set_style_property(self.detail_label, "muted", True)
        self.detail_label.hide()
        layout.addWidget(self.count_label)
        layout.addWidget(self.detail_label, stretch=1)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        layout.addLayout(self._actions)
        self.clear_button = QPushButton("✕")
        self.clear_button.setObjectName("SmallButton")
        self.clear_button.setToolTip("Quitar la selección (Esc)")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self.cleared)
        layout.addWidget(self.clear_button)

    def add_action(
        self, text: str, run: Callable[[], object], destructive: bool = False
    ) -> QPushButton:
        """A button for every chosen row; destructive ones (delete) show in red."""
        button = QPushButton(text)
        button.setObjectName("DangerButton" if destructive else "SecondaryButton")
        button.clicked.connect(lambda: run())
        self._actions.addWidget(button)
        return button

    def set_count(self, count: int, detail: str = "") -> None:
        """Shows ``count`` and an optional ``detail``, which may be rich text (colors)."""
        self.count_label.setText(f"{count} {self._chosen_word}")
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
