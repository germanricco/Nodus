"""The guided tour: the window dimmed but for one control, and a bubble saying what it is.

Each control the tour points at carries a ``coach_target`` property (``mark_target``)
instead of a new object name, since object names are what the stylesheet selects on.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.ui.theme.design import Easing, Layout, Line, Motion, Opacity, Radius, Space, motion_ms
from nodus.ui.theme.theme import Theme
from nodus.ui.widgets.style import elevate, muted_label, unit_animation

COACH_TARGET = "coach_target"


def mark_target(widget: QWidget, target: str) -> None:
    """Lets the tour point at ``widget`` as ``target``; several widgets may share one
    target (the page buttons of the sidebar), and the tour frames them together."""
    widget.setProperty(COACH_TARGET, target)


@dataclass(frozen=True)
class CoachStep:
    target: str
    title: str
    text: str


class CoachMarks(QWidget):
    """A layer over the whole ``window`` that dims it except around one step's target,
    with a bubble beside it: «3 de 7», «Anterior», «Siguiente» («Terminar» on the last
    one) and «Saltar». Esc skips; Enter or → go on; ← goes back.

    Steps whose target is not on screen (the sidebar folded, say) are left out. It
    follows its target when the window changes size, and fades in, unless the user
    asked for less motion. ``finished`` is emitted when it closes, by any way.
    """

    finished = Signal()

    def __init__(self, window: QWidget, steps: list[CoachStep], theme: Theme) -> None:
        super().__init__(window)
        self._window = window
        self._theme = theme
        self.steps = [step for step in steps if self._targets(step)]
        self.index = 0
        self._fade = 1.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Recorrido guiado")

        self.bubble = QFrame(self)
        self.bubble.setObjectName("CoachBubble")
        self.bubble.setFixedWidth(Layout.COACH_BUBBLE_WIDTH)
        layout = QVBoxLayout(self.bubble)
        layout.setContentsMargins(Space.XL, Space.L, Space.XL, Space.L)
        layout.setSpacing(Space.S)
        self.title_label = QLabel()
        self.title_label.setObjectName("DialogTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label)
        layout.addSpacing(Space.XS)
        buttons = QHBoxLayout()
        buttons.setSpacing(Space.S)
        self.count_label = muted_label("")
        buttons.addWidget(self.count_label)
        buttons.addStretch()
        self.skip_button = self._button("Saltar", "LinkButton", self.finish)
        buttons.addWidget(self.skip_button)
        self.back_button = self._button("Anterior", "SecondaryButton", self.previous)
        buttons.addWidget(self.back_button)
        self.next_button = self._button("Siguiente", "PrimaryButton", self.next)
        buttons.addWidget(self.next_button)
        layout.addLayout(buttons)
        elevate(self.bubble, theme)

        self._fade_in = unit_animation(self, Easing.SETTLE, self._set_fade)
        window.installEventFilter(self)

    def _button(self, text: str, style: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(style)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the keys belong to the tour
        button.clicked.connect(slot)
        return button

    # Running

    def start(self) -> None:
        if not self.steps:
            self.finish()
            return
        self.setGeometry(self._window.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self._show_step()
        duration = motion_ms(Motion.FAST)
        if duration > 0:
            self._fade = 0.0
            self._fade_in.setDuration(duration)
            self._fade_in.start()

    def next(self) -> None:
        if self.index == len(self.steps) - 1:
            self.finish()
            return
        self.index += 1
        self._show_step()

    def previous(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._show_step()

    def finish(self) -> None:
        self._window.removeEventFilter(self)
        self.hide()
        self.deleteLater()
        self.finished.emit()

    def _show_step(self) -> None:
        step = self.steps[self.index]
        last = self.index == len(self.steps) - 1
        self.title_label.setText(step.title)
        self.text_label.setText(step.text)
        self.count_label.setText(f"{self.index + 1} de {len(self.steps)}")
        self.back_button.setEnabled(self.index > 0)
        self.next_button.setText("Terminar" if last else "Siguiente")
        self.skip_button.setVisible(not last)
        self._place_bubble()
        self.update()

    # Geometry

    def _targets(self, step: CoachStep) -> list[QWidget]:
        return [
            widget
            for widget in self._window.findChildren(QWidget)
            if widget.property(COACH_TARGET) == step.target and widget.isVisible()
        ]

    def hole(self) -> QRect:
        """Around the step's target, in this layer's coordinates, with some air."""
        area = QRect()
        for widget in self._targets(self.steps[self.index]):
            area = area.united(
                QRect(widget.mapTo(self._window, widget.rect().topLeft()), widget.size())
            )
        return area.adjusted(-Space.S, -Space.S, Space.S, Space.S)

    def _place_bubble(self) -> None:
        """Beside the target: to its right when there is room (the sidebar), else below
        it, else above it, always inside the window."""
        self.bubble.adjustSize()
        hole, size, margin = self.hole(), self.bubble.size(), Space.L
        if hole.right() + margin + size.width() <= self.width() - margin:
            x, y = hole.right() + margin, hole.top()
        elif hole.bottom() + margin + size.height() <= self.height() - margin:
            x, y = hole.left(), hole.bottom() + margin
        else:
            x, y = hole.left(), hole.top() - margin - size.height()
        x = max(margin, min(x, self.width() - margin - size.width()))
        y = max(margin, min(y, self.height() - margin - size.height()))
        self.bubble.move(x, y)

    # Painting and input

    def _set_fade(self, value: float) -> None:
        self._fade = float(value)
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        hole = QRectF(self.hole())
        cutout = QPainterPath()
        cutout.addRoundedRect(hole, Radius.L, Radius.L)
        dimmed = QPainterPath()
        dimmed.addRect(QRectF(self.rect()))
        scrim = QColor(self._theme.shadow)
        scrim.setAlphaF(Opacity.SCRIM * self._fade)
        painter.fillPath(dimmed.subtracted(cutout), scrim)
        outline = QColor(self._theme.accent)
        outline.setAlphaF(self._fade)
        painter.setPen(QPen(outline, Line.THICK))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(cutout)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        event.accept()  # the page under the layer waits until the tour ends

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.finish()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Right):
            self.next()
        elif key == Qt.Key.Key_Left:
            self.previous()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._window and event.type() == QEvent.Type.Resize:
            self.setGeometry(self._window.rect())
            self._place_bubble()
        return super().eventFilter(watched, event)
