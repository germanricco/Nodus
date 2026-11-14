"""Primeros pasos on Inicio: the steps of a new user, ticked off as they are done."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from nodus.services.guide_service import GuideStep, GuideStepKind
from nodus.ui.pages.dashboard_cards import card_header, muted_label
from nodus.ui.theme.design import ControlSize, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.budget_bar import paint_progress
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.style import clear_layout, set_style_name, set_style_property

# What the button of each step that is still to do says.
ACTIONS = {
    GuideStepKind.ACCOUNT: "Agregar cuenta",
    GuideStepKind.EXPENSE: "Agregar gasto",
    GuideStepKind.RECURRING: "Agregar cargo",
    GuideStepKind.BUDGET: "Agregar presupuesto",
    GuideStepKind.GOAL: "Agregar meta",
    GuideStepKind.BACKUP: "Guardar copia…",
}
DONE_TEXT = "¡Listo! Ya tienes Nodus andando."


class GuideBar(QWidget):
    """How far along the steps are, in the accent color."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.fraction = 0.0
        self.setFixedHeight(ControlSize.PROGRESS_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_fraction(self, fraction: float) -> None:
        self.fraction = fraction
        self.update()

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = QRectF(0, 0, self.width(), self.height())
        paint_progress(painter, track, self.fraction, self._theme.accent, self._theme.border)
        painter.end()


class GuideCard(Card):
    """The six first steps: each one done is ticked and crossed out; the next one to do
    has a button, the later ones a link, so there is one clear thing to do. Until the
    first account exists the later steps offer nothing, since they all need one. Once
    all are done it says so, with «Cerrar». «Ocultar» puts it away at any time.

    It only shows; Inicio decides what each button opens. ``intro`` is a line under the
    title, for when the card is the whole welcome.
    """

    step_requested = Signal(object)  # GuideStepKind
    hide_requested = Signal()

    def __init__(
        self, theme_manager: ThemeManager, intro: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        header = card_header(self, "Primeros pasos")
        self.count_label = muted_label("")
        header.addWidget(self.count_label)
        self.hide_button = QPushButton("Ocultar")
        self.hide_button.setObjectName("LinkButton")
        self.hide_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_button.clicked.connect(self.hide_requested)
        header.addWidget(self.hide_button)
        if intro:
            intro_label = muted_label(intro)
            intro_label.setWordWrap(True)
            self.body.addWidget(intro_label)
        self.bar = GuideBar(theme_manager.theme)
        theme_manager.theme_changed.connect(self.bar.set_theme)
        self.body.addWidget(self.bar)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(Space.XS)
        self.body.addLayout(self._rows)
        self.buttons: dict[GuideStepKind, QPushButton] = {}

    def show_steps(self, steps: list[GuideStep]) -> None:
        done = sum(step.done for step in steps)
        self.count_label.setText(f"{done} de {len(steps)}")
        self.bar.set_fraction(done / len(steps) if steps else 0)
        clear_layout(self._rows)
        self.buttons = {}
        if done == len(steps):
            self._rows.addLayout(self._finished_row())
            return
        first_to_do = next(step.kind for step in steps if not step.done)
        has_account = steps[0].done
        for step in steps:
            if step.done:
                self._rows.addLayout(self._step_row(step, "", "✓"))
            elif step.kind is first_to_do:
                self._rows.addLayout(self._step_row(step, "PrimaryButton", "○"))
            else:
                self._rows.addLayout(self._step_row(step, "LinkButton" if has_account else "", "○"))

    def _step_row(self, step: GuideStep, button_style: str, mark: str) -> QHBoxLayout:
        """A step's line, with a button of ``button_style`` that takes it, if any."""
        row = QHBoxLayout()
        row.setSpacing(Space.S)
        label = QLabel(f"{mark}  {step.title}")
        set_style_property(label, "done", step.done)
        label.setAccessibleName(f"{step.title}: {'hecho' if step.done else 'falta'}")
        row.addWidget(label)
        row.addStretch()
        if button_style:
            button = QPushButton(ACTIONS[step.kind])
            set_style_name(button, button_style)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda: self.step_requested.emit(step.kind))
            self.buttons[step.kind] = button
            row.addWidget(button)
        return row

    def _finished_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(DONE_TEXT))
        row.addStretch()
        self.close_button = QPushButton("Cerrar")
        set_style_name(self.close_button, "SecondaryButton")
        self.close_button.clicked.connect(self.hide_requested)
        row.addWidget(self.close_button)
        return row
