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
from nodus.ui.theme.icons import icon, logo_pixmap
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.money_label import MoneyLabel
from nodus.ui.widgets.style import clear_layout, set_style_property


class Sidebar(QFrame):
    """Navigation buttons on top, the user's accounts below, like MoneyMatter's sidebar.

    It can collapse to its icons, to leave the room to the page; the choice is saved.
    """

    page_requested = Signal(object)  # PageId

    WIDTH = 260
    COLLAPSED_WIDTH = 64
    LOGO_SIZE = 28

    def __init__(self, services: Services, event_bus: EventBus, theme_manager: ThemeManager):
        super().__init__()
        self._services = services
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 8)
        layout.setSpacing(2)

        layout.addWidget(self._build_logo())

        self._nav_buttons = self._build_nav_buttons(layout)

        self._accounts_title = QLabel("CUENTAS")
        self._accounts_title.setObjectName("SectionLabel")
        layout.addWidget(self._accounts_title)
        self._accounts_area = self._build_accounts_area()
        layout.addWidget(self._accounts_area, stretch=1)
        layout.addStretch()  # keeps the buttons on top while the accounts are hidden

        layout.addLayout(self._build_footer())

        self._theme = theme_manager.theme
        self._collapsed = False
        self.set_collapsed(services.settings.sidebar_collapsed())
        self._apply_theme(theme_manager.theme)
        theme_manager.theme_changed.connect(self._apply_theme)
        event_bus.accounts_changed.connect(self.refresh_accounts)
        event_bus.transactions_changed.connect(self.refresh_accounts)
        self.refresh_accounts()

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Shows only the icons (with the names as tooltips), or everything."""
        self._collapsed = collapsed
        self.setFixedWidth(self.COLLAPSED_WIDTH if collapsed else self.WIDTH)
        for page_id, button in self._nav_buttons.items():
            button.setText("" if collapsed else page_id.label)
            button.setToolTip(page_id.label if collapsed else "")
            set_style_property(button, "collapsed", collapsed)
        for widget in (self._logo_name, self._accounts_title, self._accounts_area, self._footer):
            widget.setVisible(not collapsed)
        self._logo_row.setContentsMargins(*((2, 4, 2, 12) if collapsed else (8, 4, 8, 12)))
        self.collapse_button.setToolTip("Expandir el panel" if collapsed else "Contraer el panel")
        self._apply_collapse_icon()

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)
        self._services.settings.set_sidebar_collapsed(self._collapsed)

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

    def _build_logo(self) -> QWidget:
        logo = QWidget()
        row = QHBoxLayout(logo)
        row.setContentsMargins(8, 4, 8, 12)
        row.setSpacing(10)
        image = QLabel()
        image.setPixmap(logo_pixmap(self.LOGO_SIZE))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(image)
        self._logo_name = QLabel("Nodus")
        self._logo_name.setObjectName("SidebarLogo")
        row.addWidget(self._logo_name, stretch=1)
        self._logo_row = row
        return logo

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self._footer = QLabel(f"Nodus {__version__}")
        self._footer.setObjectName("SidebarFooter")
        row.addWidget(self._footer, stretch=1)
        self.collapse_button = QPushButton()
        self.collapse_button.setObjectName("IconButton")
        self.collapse_button.setIconSize(QSize(18, 18))
        self.collapse_button.setFixedSize(34, 34)
        self.collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        row.addWidget(self.collapse_button)
        return row

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
        self._theme = theme
        for page_id, button in self._nav_buttons.items():
            button.setIcon(icon(page_id.icon_name, theme.text_muted, checked_color=theme.accent))
        self._apply_collapse_icon()

    def _apply_collapse_icon(self) -> None:
        name = "panel-left-open" if self._collapsed else "panel-left-close"
        self.collapse_button.setIcon(icon(name, self._theme.text_muted))
