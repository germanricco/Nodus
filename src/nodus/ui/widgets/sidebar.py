"""Left sidebar: navigation and the list of accounts with their balances."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus import __version__
from nodus.models.money import Money
from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.theme.icons import icon
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.money_label import MoneyLabel
from nodus.ui.widgets.style import clear_layout, set_style_property


class Sidebar(QFrame):
    """Navigation buttons on top, the user's accounts below, like MoneyMatter's sidebar."""

    page_requested = Signal(object)  # PageId

    WIDTH = 260

    def __init__(self, services: Services, event_bus: EventBus, theme_manager: ThemeManager):
        super().__init__()
        self._services = services
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 8)
        layout.setSpacing(2)

        logo = QLabel("Nodus")
        logo.setObjectName("SidebarLogo")
        layout.addWidget(logo)

        self._nav_buttons = self._build_nav_buttons(layout)

        accounts_title = QLabel("CUENTAS")
        accounts_title.setObjectName("SectionLabel")
        layout.addWidget(accounts_title)
        layout.addWidget(self._build_accounts_area(), stretch=1)

        footer = QLabel(f"Nodus {__version__}")
        footer.setObjectName("SidebarFooter")
        layout.addWidget(footer)

        self._apply_theme(theme_manager.theme)
        theme_manager.theme_changed.connect(self._apply_theme)
        event_bus.accounts_changed.connect(self.refresh_accounts)
        event_bus.transactions_changed.connect(self.refresh_accounts)
        self.refresh_accounts()

    def select(self, page_id: PageId) -> None:
        self._nav_buttons[page_id].setChecked(True)

    def nav_button(self, page_id: PageId) -> QPushButton:
        return self._nav_buttons[page_id]

    def refresh_accounts(self) -> None:
        """Rebuilds the account list from the database."""
        clear_layout(self._accounts_layout)
        accounts = self._services.accounts.list_accounts()
        if not accounts:
            empty = QLabel("Todavía no hay cuentas")
            empty.setObjectName("SidebarItem")
            set_style_property(empty, "muted", True)
            self._accounts_layout.addWidget(empty)
        balances = self._services.accounts.balances()
        for account in accounts:
            self._accounts_layout.addWidget(self._account_row(account.name, balances[account.id]))
        self._accounts_layout.addStretch()

    def _build_nav_buttons(self, layout: QVBoxLayout) -> dict[PageId, QPushButton]:
        group = QButtonGroup(self)
        buttons = {}
        for page_id in PageId:
            button = QPushButton(page_id.label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIconSize(QSize(20, 20))
            button.clicked.connect(lambda _checked, p=page_id: self.page_requested.emit(p))
            group.addButton(button)
            layout.addWidget(button)
            buttons[page_id] = button
        return buttons

    def _build_accounts_area(self) -> QScrollArea:
        container = QWidget()
        container.setObjectName("SidebarAccounts")
        self._accounts_layout = QVBoxLayout(container)
        self._accounts_layout.setContentsMargins(0, 0, 0, 0)
        self._accounts_layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setObjectName("SidebarAccounts")
        scroll.setWidget(container)
        return scroll

    @staticmethod
    def _account_row(name: str, balance: Money) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 4, 2)
        label = QLabel(name)
        label.setObjectName("SidebarItem")
        layout.addWidget(label, stretch=1)
        layout.addWidget(MoneyLabel(balance))
        return row

    def _apply_theme(self, theme: Theme) -> None:
        for page_id, button in self._nav_buttons.items():
            button.setIcon(icon(page_id.icon_name, theme.text_muted, checked_color=theme.accent))
