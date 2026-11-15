"""Short notices of what just happened, at the bottom right of the page, that go away
on their own: «Copia guardada.», «Se omitió Internet.» with «Deshacer».

The bell keeps what is still pending; a toast tells what was just done, so it never
asks for a decision and never takes the focus.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.ui.theme.design import Dwell, IconSize, Layout, Space
from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.style import elevate

MAX_TOASTS = 3


class Toast(QFrame):
    """One notice: its text, an optional action such as «Deshacer», and «✕». It closes
    after ``Dwell.TOAST`` (``Dwell.TOAST_ACTION`` with an action, to leave time to use
    it); under the mouse it waits, and leaving gives it its whole time again."""

    closed = Signal()

    def __init__(
        self,
        text: str,
        theme_manager: ThemeManager,
        action_text: str | None = None,
        on_action: Callable[[], object] | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("Toast")
        self.setFixedWidth(Layout.TOAST_WIDTH)
        self.text = text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.L, Space.M, Space.S, Space.M)
        layout.setSpacing(Space.M)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        layout.addWidget(self.label, stretch=1)
        self.action_button: QPushButton | None = None
        if action_text is not None and on_action is not None:
            self.action_button = QPushButton(action_text)
            self.action_button.setObjectName("LinkButton")
            self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_button.clicked.connect(lambda: self._act(on_action))
            layout.addWidget(self.action_button)
        self.close_button = QPushButton()
        self.close_button.setObjectName("PanelClose")
        self.close_button.setIcon(icon("close", theme_manager.theme.text_muted))
        self.close_button.setIconSize(QSize(IconSize.M, IconSize.M))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setToolTip("Cerrar")
        self.close_button.clicked.connect(self.dismiss)
        layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignTop)
        elevate(self, theme_manager.theme)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(Dwell.TOAST_ACTION if self.action_button else Dwell.TOAST)
        self._timer.timeout.connect(self.dismiss)
        self._timer.start()

    @property
    def waiting(self) -> bool:
        """Whether it is counting down to close."""
        return self._timer.isActive()

    def restart(self) -> None:
        """Gives it its whole time again, as when the same notice comes back."""
        self._timer.start()

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self._timer.start()
        super().leaveEvent(event)

    def _act(self, on_action: Callable[[], object]) -> None:
        self.dismiss()
        on_action()

    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()
        self.closed.emit()


class ToastStack(QWidget):
    """The toasts of a page area, stacked at its bottom right with the newest last. It
    keeps ``MAX_TOASTS`` at most, and a notice equal to one on screen replaces it."""

    def __init__(self, area: QWidget, theme_manager: ThemeManager) -> None:
        super().__init__(area)
        self._area = area
        self._theme_manager = theme_manager
        self.toasts: list[Toast] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Space.S)
        area.installEventFilter(self)
        self.hide()

    def show_toast(
        self,
        text: str,
        action_text: str | None = None,
        on_action: Callable[[], object] | None = None,
    ) -> Toast:
        for old in self.toasts:
            if old.text == text:
                self._remove(old)
        toast = Toast(text, self._theme_manager, action_text, on_action)
        toast.closed.connect(lambda: self._remove(toast))
        self.toasts.append(toast)
        self._layout.addWidget(toast)
        toast.show()  # now, not on the next turn of the event loop, so it is measured
        while len(self.toasts) > MAX_TOASTS:
            self._remove(self.toasts[0])
        self._place()
        return toast

    def _remove(self, toast: Toast) -> None:
        if toast not in self.toasts:
            return
        self.toasts.remove(toast)
        toast.hide()
        self._layout.removeWidget(toast)
        toast.setParent(None)
        toast.deleteLater()
        self._place()

    def _place(self) -> None:
        if not self.toasts:
            self.hide()
            return
        # Shown first: a hidden layout has not measured its wrapped texts yet.
        self.show()
        self.raise_()
        self._layout.activate()
        width = Layout.TOAST_WIDTH
        if self._layout.hasHeightForWidth():
            height = self._layout.totalHeightForWidth(width)
        else:
            height = self._layout.totalSizeHint().height()
        area = self._area.rect()
        self.setGeometry(
            area.width() - width - Space.L, area.height() - height - Space.L, width, height
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._area and event.type() == QEvent.Type.Resize:
            self._place()
        return False


def show_toast(
    widget: QWidget,
    text: str,
    action_text: str | None = None,
    on_action: Callable[[], object] | None = None,
) -> None:
    """Shows ``text`` in the toasts of ``widget``'s window. A widget outside the main
    window, such as a dialog opened alone in a test, has none, and nothing shows."""
    for candidate in (widget.window(), widget.window().parentWidget()):
        toast = getattr(candidate, "toast", None) if candidate is not None else None
        if callable(toast):
            toast(text, action_text, on_action)
            return
