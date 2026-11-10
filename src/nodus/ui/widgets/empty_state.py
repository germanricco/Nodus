"""What a list, a card or a page says when it has nothing to show, with the next step at
hand. It is the only empty state of the app, so they all read and look alike."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.style import set_style_name, set_style_property

# A card about a period with no movements: the Dashboard's and Análisis's.
NO_MOVEMENTS_TEXT = "Sin movimientos en el período."


class EmptyState(QWidget):
    """A centered message and, when there is one, a button with the next step: «Limpiar
    filtros» when filters leave nothing, «Agregar beneficiario» when there are none yet.
    A message alone leaves the user to find the way out.

    A list's empty state fills the room its rows would take. A ``compact`` one sits
    inside a card or a panel (a chart with no data, a list of rates) with less air. A
    page with nothing yet puts a ``title`` over the message, saying what goes there.
    """

    def __init__(self, text: str = "", compact: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(Space.S if compact else Space.M)
        if compact:
            layout.setContentsMargins(0, Space.M, 0, Space.M)
        else:
            layout.addStretch()
        self.title = QLabel()
        self.title.setObjectName("EmptyStateTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.hide()
        layout.addWidget(self.title)
        self.label = QLabel()
        self.label.setObjectName("EmptyState")
        set_style_property(self.label, "compact", compact)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.action_button = QPushButton()
        self.action_button.clicked.connect(self._run_action)
        self.action_button.hide()
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        if not compact:
            layout.addStretch()
        self._action: Callable[[], object] | None = None
        self.set_message(text)

    def text(self) -> str:
        return self.label.text()

    def set_message(
        self,
        text: str,
        action: str = "",
        run: Callable[[], object] | None = None,
        title: str = "",
        primary: bool = False,
    ) -> None:
        """Shows ``text`` under ``title``, if any, and, if ``action`` is given, a button
        that calls ``run``: ``primary`` when it is the one thing to do on the page."""
        self.title.setText(title)
        self.title.setVisible(bool(title))
        self.label.setText(text)
        self.action_button.setText(action)
        set_style_name(self.action_button, "PrimaryButton" if primary else "SecondaryButton")
        self.action_button.setVisible(bool(action))
        self._action = run

    def _run_action(self) -> None:
        if self._action is not None:
            self._action()


def empty_page_card(
    title: str,
    text: str,
    action: str = "",
    run: Callable[[], object] | None = None,
) -> tuple[Card, EmptyState]:
    """What a page shows while it has nothing yet: a card saying what goes there and why,
    with the way to add the first one when the page has it."""
    state = EmptyState(compact=True)
    state.set_message(text, action, run, title=title, primary=True)
    card = Card()
    card.body.addWidget(state)
    return card, state
