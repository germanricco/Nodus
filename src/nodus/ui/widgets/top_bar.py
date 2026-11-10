"""Bar above every page with the main action, notifications and settings."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from nodus.ui.theme.design import ControlSize, IconSize, Space
from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager


class TopBar(QFrame):
    """ "Agregar transacción" on the left, always visible because it is the most frequent
    action; on the right, the eye that hides amounts, sending comments and the
    notifications bell with how many there are. Ajustes is at the foot of the sidebar."""

    add_transaction_requested = Signal()
    hide_amounts_toggled = Signal()
    feedback_requested = Signal()
    notifications_requested = Signal()

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.setObjectName("TopBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.XXL, Space.M, Space.XXL, Space.M)
        layout.setSpacing(Space.S)

        self._add_button = QPushButton("Agregar transacción")
        self._add_button.setObjectName("PrimaryButton")
        self._add_button.setIconSize(QSize(IconSize.L, IconSize.L))
        self._add_button.clicked.connect(self.add_transaction_requested)
        layout.addWidget(self._add_button)
        layout.addStretch()

        self.feedback_button = self._icon_button("Enviar comentarios")
        self.feedback_button.clicked.connect(self.feedback_requested)
        self.notifications_button = self._icon_button("Notificaciones")
        self.notifications_button.clicked.connect(self.notifications_requested)
        self.notification_count = QLabel(self.notifications_button)
        self.notification_count.setObjectName("NotificationCount")
        self.notification_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_count.setFixedSize(
            ControlSize.NOTIFICATION_COUNT, ControlSize.NOTIFICATION_COUNT
        )
        self.notification_count.move(22, -2)  # geometry: over the corner of the bell
        self.notification_count.hide()
        self.hide_amounts_button = self._icon_button("")
        self.hide_amounts_button.clicked.connect(self.hide_amounts_toggled)
        self._amounts_hidden = False
        layout.addWidget(self.hide_amounts_button)
        layout.addWidget(self.feedback_button)
        layout.addWidget(self.notifications_button)

        self._apply_theme(theme_manager.theme)
        theme_manager.theme_changed.connect(self._apply_theme)

    def set_amounts_hidden(self, hidden: bool) -> None:
        """Shows the eye that would undo the current state."""
        self._amounts_hidden = hidden
        self.hide_amounts_button.setToolTip("Mostrar montos" if hidden else "Ocultar montos")
        self._apply_theme(self._theme)

    def set_notification_count(self, count: int) -> None:
        self.notification_count.setText(str(count) if count < 10 else "9+")
        self.notification_count.setVisible(count > 0)

    @staticmethod
    def _icon_button(tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("IconButton")
        button.setToolTip(tooltip)
        button.setIconSize(QSize(IconSize.XL, IconSize.XL))
        button.setFixedSize(ControlSize.TOP_BAR_BUTTON, ControlSize.TOP_BAR_BUTTON)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _apply_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._add_button.setIcon(icon("plus", theme.on_accent))
        eye = "eye-off" if self._amounts_hidden else "eye"
        self.hide_amounts_button.setIcon(icon(eye, theme.text_muted))
        self.feedback_button.setIcon(icon("message", theme.text_muted))
        self.notifications_button.setIcon(icon("bell", theme.text_muted))
