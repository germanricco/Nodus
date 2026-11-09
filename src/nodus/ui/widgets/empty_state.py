"""What a list says when it has nothing to show, with the next step at hand."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space


class EmptyState(QWidget):
    """A centered message where the rows would be and, when there is one, a button with the
    next step: «Limpiar filtros» when filters leave nothing, «Agregar beneficiario» when
    there are none yet. A message alone leaves the user to find the way out."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(Space.M)
        layout.addStretch()
        self.label = QLabel()
        self.label.setObjectName("EmptyState")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.action_button = QPushButton()
        self.action_button.setObjectName("SecondaryButton")
        self.action_button.clicked.connect(self._run_action)
        self.action_button.hide()
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        self._action: Callable[[], object] | None = None

    def text(self) -> str:
        return self.label.text()

    def set_message(
        self, text: str, action: str = "", run: Callable[[], object] | None = None
    ) -> None:
        """Shows ``text`` and, if ``action`` is given, a button that calls ``run``."""
        self.label.setText(text)
        self.action_button.setText(action)
        self.action_button.setVisible(bool(action))
        self._action = run

    def _run_action(self) -> None:
        if self._action is not None:
            self._action()
