"""Bar above every page with the main action, notifications and settings."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager


class TopBar(QFrame):
    """ "Agregar transacción" on the left, always visible because it is the most frequent
    action; the notifications bell, with how many there are, and settings on the right."""

    add_transaction_requested = Signal()
    notifications_requested = Signal()
    settings_requested = Signal()

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.setObjectName("TopBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(8)

        self._add_button = QPushButton("Agregar transacción")
        self._add_button.setObjectName("PrimaryButton")
        self._add_button.setIconSize(QSize(18, 18))
        self._add_button.clicked.connect(self.add_transaction_requested)
        layout.addWidget(self._add_button)
        layout.addStretch()

        self.notifications_button = self._icon_button("Notificaciones")
        self.notifications_button.clicked.connect(self.notifications_requested)
        self.notification_count = QLabel(self.notifications_button)
        self.notification_count.setObjectName("NotificationCount")
        self.notification_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_count.setFixedSize(18, 18)
        self.notification_count.move(22, -2)
        self.notification_count.hide()
        self.settings_button = self._icon_button("Ajustes")
        self.settings_button.clicked.connect(self.settings_requested)
        layout.addWidget(self.notifications_button)
        layout.addWidget(self.settings_button)

        self._apply_theme(theme_manager.theme)
        theme_manager.theme_changed.connect(self._apply_theme)

    def set_notification_count(self, count: int) -> None:
        self.notification_count.setText(str(count) if count < 10 else "9+")
        self.notification_count.setVisible(count > 0)

    @staticmethod
    def _icon_button(tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("IconButton")
        button.setToolTip(tooltip)
        button.setIconSize(QSize(20, 20))
        button.setFixedSize(38, 38)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _apply_theme(self, theme: Theme) -> None:
        self._add_button.setIcon(icon("plus", theme.on_accent))
        self.notifications_button.setIcon(icon("bell", theme.text_muted))
        self.settings_button.setIcon(icon("settings", theme.text_muted))
