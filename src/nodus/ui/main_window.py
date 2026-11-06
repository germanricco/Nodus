"""Main application window."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nodus.models.period import Month
from nodus.services.container import Services
from nodus.services.update_service import Release
from nodus.ui.background import BackgroundCall
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.pages.accounts_page import AccountsPage
from nodus.ui.pages.categories_page import CategoriesPage
from nodus.ui.pages.dashboard_page import DashboardPage
from nodus.ui.pages.page import Page
from nodus.ui.pages.settings_page import SettingsPage
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.sidebar import Sidebar
from nodus.ui.widgets.top_bar import TopBar
from nodus.ui.widgets.update_banner import UpdateBanner


class MainWindow(QMainWindow):
    """Sidebar on the left; top bar and the current page on the right."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__()
        self._services = services
        self._event_bus = event_bus
        self.setWindowTitle("Nodus")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self.sidebar = Sidebar(services, event_bus, theme_manager)
        self.top_bar = TopBar(theme_manager)
        self.update_banner = UpdateBanner()
        self._stack = QStackedWidget()
        self._stack.setObjectName("PageStack")
        dashboard = DashboardPage(services, event_bus, theme_manager)
        dashboard.navigate_requested.connect(self.show_page)
        dashboard.transactions_requested.connect(self.show_transactions)
        self._pages: dict[PageId, Page] = {
            PageId.DASHBOARD: dashboard,
            PageId.ACCOUNTS: AccountsPage(services, event_bus),
            PageId.TRANSACTIONS: TransactionsPage(services, event_bus, theme_manager),
            PageId.CATEGORIES: CategoriesPage(services, event_bus),
            PageId.SETTINGS: SettingsPage(services, event_bus, theme_manager),
        }
        for page in self._pages.values():
            self._stack.addWidget(page)

        content = QWidget()
        content.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.top_bar)
        content_layout.addWidget(self.update_banner)
        content_layout.addWidget(self._stack, stretch=1)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(content, stretch=1)
        self.setCentralWidget(central)

        self.sidebar.page_requested.connect(self.show_page)
        self.top_bar.add_transaction_requested.connect(self.open_new_transaction)
        self.show_page(PageId.DASHBOARD)

    def check_for_updates(self) -> None:
        """Looks for a new version in the background, unless the user turned it off.

        Called by the app once the window is open, not on construction, so tests and
        screenshots never reach the network."""
        if not self._services.settings.check_updates():
            return
        self._update_check = BackgroundCall(self._services.updates.check, parent=self)
        self._update_check.done.connect(self._show_release)
        self._update_check.start()

    def _show_release(self, release: Release | None) -> None:
        if release is not None:
            self.update_banner.show_release(release)

    @property
    def current_page(self) -> Page:
        return self._stack.currentWidget()

    def page(self, page_id: PageId) -> Page:
        return self._pages[page_id]

    def show_page(self, page_id: PageId) -> None:
        page = self._pages[page_id]
        page.refresh()
        self._stack.setCurrentWidget(page)
        self.sidebar.select(page_id)

    def show_transactions(self, month: Month) -> None:
        """Opens the transactions page on ``month``."""
        self._pages[PageId.TRANSACTIONS].month_selector.set_month(month)
        self.show_page(PageId.TRANSACTIONS)

    def open_new_transaction(self) -> None:
        """Opens the transaction dialog, or leads to Cuentas when there is nowhere to record it."""
        if not self._services.accounts.list_accounts():
            QMessageBox.information(
                self,
                "Primero, una cuenta",
                "Para registrar transacciones necesitas al menos una cuenta activa."
                " Crea una en Cuentas y vuelve a intentarlo.",
            )
            self.show_page(PageId.ACCOUNTS)
            return
        TransactionDialog(self._services, self._event_bus, parent=self).exec()
