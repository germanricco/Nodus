"""Bar above every page with the main action."""

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton

from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager


class TopBar(QFrame):
    """Holds "Agregar transacción", always visible because it is the most frequent action."""

    add_transaction_requested = Signal()

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.setObjectName("TopBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)

        self._add_button = QPushButton("Agregar transacción")
        self._add_button.setObjectName("PrimaryButton")
        self._add_button.setIconSize(QSize(18, 18))
        self._add_button.clicked.connect(self.add_transaction_requested)
        layout.addWidget(self._add_button)
        layout.addStretch()

        self._apply_theme(theme_manager.theme)
        theme_manager.theme_changed.connect(self._apply_theme)

    def _apply_theme(self, theme: Theme) -> None:
        self._add_button.setIcon(icon("plus", theme.on_accent))
