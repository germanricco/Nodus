"""Main application window."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nodus.links import feedback_url
from nodus.models.period import Month
from nodus.services.container import Services
from nodus.services.notification_service import Notice, NoticeKind
from nodus.services.update_service import Release
from nodus.ui.background import BackgroundCall
from nodus.ui.browser import open_url
from nodus.ui.dialogs.news_dialog import NewsDialog
from nodus.ui.dialogs.transaction_dialog import TransactionDialog
from nodus.ui.dialogs.update_dialog import UpdateDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.accounts_page import AccountsPage
from nodus.ui.pages.analysis_page import AnalysisPage
from nodus.ui.pages.budgets_page import BudgetsPage
from nodus.ui.pages.categories_page import CategoriesPage
from nodus.ui.pages.dashboard_page import DashboardPage
from nodus.ui.pages.page import Page
from nodus.ui.pages.payees_page import PayeesPage
from nodus.ui.pages.recurring_page import RecurringPage
from nodus.ui.pages.settings_page import SettingsPage
from nodus.ui.pages.tags_page import TagsPage
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.rate_updater import RateUpdater
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.notification_panel import NotificationPanel
from nodus.ui.widgets.sidebar import Sidebar
from nodus.ui.widgets.top_bar import TopBar


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

        self.theme_manager = theme_manager
        self.sidebar = Sidebar(services, event_bus, theme_manager)
        self.top_bar = TopBar(theme_manager)
        self.notification_panel = NotificationPanel(self)
        self.notification_panel.action_requested.connect(self._act_on_notice)
        self.notification_panel.dismiss_requested.connect(self._dismiss_notice)
        self.notification_panel.news_requested.connect(self._show_release_news)
        self._release: Release | None = None
        self._stack = QStackedWidget()
        self._stack.setObjectName("PageStack")
        dashboard = DashboardPage(services, event_bus, theme_manager)
        dashboard.navigate_requested.connect(self.show_page)
        accounts = AccountsPage(services, event_bus, theme_manager)
        accounts.navigate_requested.connect(self.show_page)
        accounts.transactions_requested.connect(self.show_transactions)
        categories = CategoriesPage(services, event_bus)
        categories.transactions_requested.connect(self.show_transactions)
        dashboard.transactions_requested.connect(self.show_transactions)
        budgets = BudgetsPage(services, event_bus, theme_manager)
        budgets.transactions_requested.connect(self.show_transactions)
        dashboard.budgets_requested.connect(self.show_budgets)
        analysis = AnalysisPage(services, event_bus, theme_manager)
        analysis.transactions_requested.connect(self.show_transactions)
        analysis.navigate_requested.connect(self.show_page)
        payees = PayeesPage(services, event_bus, theme_manager)
        payees.transactions_requested.connect(self.show_transactions)
        tags = TagsPage(services, event_bus, theme_manager)
        tags.transactions_requested.connect(self.show_transactions)
        transactions = TransactionsPage(services, event_bus, theme_manager)
        transactions.navigate_requested.connect(self.show_page)
        self._pages: dict[PageId, Page] = {
            PageId.DASHBOARD: dashboard,
            PageId.ACCOUNTS: accounts,
            PageId.TRANSACTIONS: transactions,
            PageId.RECURRING: RecurringPage(services, event_bus),
            PageId.BUDGETS: budgets,
            PageId.ANALYSIS: analysis,
            PageId.CATEGORIES: categories,
            PageId.PAYEES: payees,
            PageId.TAGS: tags,
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
        self.top_bar.notifications_requested.connect(self.open_notifications)
        self.top_bar.feedback_requested.connect(lambda: open_url(feedback_url()))
        self.top_bar.set_amounts_hidden(services.settings.amounts_hidden())
        self.top_bar.hide_amounts_toggled.connect(self.toggle_amounts_hidden)
        for signal in (
            event_bus.exchange_rates_changed,
            event_bus.accounts_changed,
            event_bus.recurring_changed,
            event_bus.transactions_changed,
            event_bus.budgets_changed,
            event_bus.categories_changed,
        ):
            signal.connect(self.refresh_notifications)
        self.show_page(PageId.DASHBOARD)
        self.refresh_notifications()

    def check_for_updates(self) -> None:
        """Looks for a new version in the background, unless the user turned it off.

        Called by the app once the window is open, not on construction, so tests and
        screenshots never reach the network."""
        if not self._services.settings.check_updates():
            return
        self._update_check = BackgroundCall(self._services.updates.check, parent=self)
        self._update_check.done.connect(self._show_release)
        self._update_check.start()

    def update_exchange_rate(self) -> None:
        """Brings today's dollar rate in the background when the source is automatic.

        Called by the app once the window is open, like ``check_for_updates``."""
        self._rate_updater = RateUpdater(self._services, self._event_bus, parent=self)
        self._rate_updater.update()

    def show_unseen_news(self) -> None:
        """After an update, tells once what changed since the version opened last.

        Called by the app once the window is open, like ``check_for_updates``."""
        entries = self._services.news.take_unseen()
        if entries:
            NewsDialog.for_entries(entries, parent=self).exec()

    def _show_release(self, release: Release | None) -> None:
        self._release = release
        self.refresh_notifications()

    # Notifications

    def notices(self) -> list[Notice]:
        return self._services.notifications.notices(date.today(), self._release)

    def refresh_notifications(self) -> None:
        """Updates the count on the bell, and the panel if it is open."""
        notices = self.notices()
        self.top_bar.set_notification_count(len(notices))
        if self.notification_panel.isVisible():
            self.notification_panel.set_notices(notices)

    def toggle_amounts_hidden(self) -> None:
        """Hides balances and the net worth, or shows them again; the choice is saved."""
        hidden = not self._services.settings.amounts_hidden()
        self._services.settings.set_amounts_hidden(hidden)
        self.top_bar.set_amounts_hidden(hidden)
        self._event_bus.amounts_hidden_changed.emit(hidden)

    def open_notifications(self) -> None:
        self.notification_panel.set_notices(self.notices())
        self.notification_panel.open_below(self.top_bar.notifications_button)

    def _act_on_notice(self, notice: Notice) -> None:
        if notice.kind is NoticeKind.UPDATE and self._release is not None:
            self.start_update(self._release)
        elif notice.kind is NoticeKind.CHARGES_DUE:
            self.show_page(PageId.RECURRING)
        elif notice.kind is NoticeKind.BUDGET_OVER:
            self.show_budgets(Month.of(date.today()))
        else:
            self.show_page(PageId.SETTINGS)

    def _show_release_news(self, _notice: Notice) -> None:
        if self._release is None:
            return
        dialog = NewsDialog.for_release(self._release, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.start_update(self._release)

    def start_update(self, release: Release) -> None:
        """Downloads and installs ``release``, then closes Nodus for the installer, which
        opens it again. Run from the source code, or without an installer attached, the
        release page opens instead."""
        if not self._services.updates.can_install(release):
            open_url(release.url)
            return
        dialog = UpdateDialog(self._services.updates, release, parent=self)
        dialog.exec()
        if dialog.installing:
            QApplication.quit()

    def _dismiss_notice(self, _notice: Notice) -> None:
        if self._release is not None:
            self._services.notifications.dismiss(self._release)
        self.refresh_notifications()

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

    def show_transactions(self, focus: TransactionFocus) -> None:
        """Opens the transactions page on what ``focus`` asks for."""
        self._pages[PageId.TRANSACTIONS].focus(focus)
        self.show_page(PageId.TRANSACTIONS)

    def show_budgets(self, month: Month) -> None:
        """Opens the budgets page on ``month``."""
        self._pages[PageId.BUDGETS].show_month(month)
        self.show_page(PageId.BUDGETS)

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
        TransactionDialog(self._services, self._event_bus, self.theme_manager, parent=self).exec()
