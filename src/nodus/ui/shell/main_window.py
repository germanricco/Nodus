"""Main application window."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nodus import APP_NAME
from nodus.links import feedback_url
from nodus.models.period import Month
from nodus.services.app.notification_service import Notice
from nodus.services.container import Services
from nodus.services.external.update_service import Release
from nodus.ui.background import BackgroundCall
from nodus.ui.browser import open_url
from nodus.ui.dialogs.confirm import ask
from nodus.ui.dialogs.news_dialog import NewsDialog
from nodus.ui.dialogs.transaction_dialog import TransactionDialog, TransactionStart
from nodus.ui.dialogs.update_dialog import UpdateDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, PageId, TransactionFocus
from nodus.ui.pages.account_detail_page import AccountDetailPage
from nodus.ui.pages.accounts_page import AccountsPage
from nodus.ui.pages.analysis.analysis_page import AnalysisPage
from nodus.ui.pages.base.detail_page import DetailPage
from nodus.ui.pages.base.page import Page
from nodus.ui.pages.budgets_page import BudgetsPage
from nodus.ui.pages.categories_page import CategoriesPage
from nodus.ui.pages.dashboard.dashboard_page import DashboardPage
from nodus.ui.pages.goal_detail_page import GoalDetailPage
from nodus.ui.pages.goals_page import GoalsPage
from nodus.ui.pages.payee_detail_page import PayeeDetailPage
from nodus.ui.pages.payees_page import PayeesPage
from nodus.ui.pages.recurring_page import RecurringPage
from nodus.ui.pages.settings_page import SettingsPage
from nodus.ui.pages.tag_detail_page import TagDetailPage
from nodus.ui.pages.tags_page import TagsPage
from nodus.ui.pages.transactions_page import TransactionsPage
from nodus.ui.rate_updater import RateUpdater, updated_text
from nodus.ui.shell.coach_marks import CoachMarks
from nodus.ui.shell.help_panel import HelpPanel
from nodus.ui.shell.notices import NOTICES
from nodus.ui.shell.notification_panel import NotificationPanel
from nodus.ui.shell.sidebar import Sidebar
from nodus.ui.shell.top_bar import TopBar
from nodus.ui.shell.tour import TOUR_STEPS
from nodus.ui.shortcuts import HELP, UNDO
from nodus.ui.text.help_texts import HelpTopic, topic_for_page
from nodus.ui.text.labels import TOUR_LABEL
from nodus.ui.theme.design import Layout
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.undo import undo
from nodus.ui.widgets.toast import ToastStack


class MainWindow(QMainWindow):
    """Sidebar on the left; top bar and the current page on the right."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__()
        self._services = services
        self._event_bus = event_bus
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(*Layout.WINDOW_MIN_SIZE)
        self.resize(*Layout.WINDOW_SIZE)

        self.theme_manager = theme_manager
        self.sidebar = Sidebar(services, event_bus, theme_manager)
        self.top_bar = TopBar(theme_manager)
        self.notification_panel = NotificationPanel(self)
        self.notification_panel.action_requested.connect(self._act_on_notice)
        self.notification_panel.dismiss_requested.connect(self._dismiss_notice)
        self.notification_panel.news_requested.connect(self._show_release_news)
        self._stack = QStackedWidget()
        self._stack.setObjectName("PageStack")
        # Built the first time each one is shown (``page``, ``detail``): opening the
        # window only pays for Inicio.
        self._pages: dict[PageId, Page] = {}
        self._details: dict[DetailId, DetailPage] = {}

        content = QWidget()
        content.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.top_bar)
        content_layout.addWidget(self._stack, stretch=1)
        self.toasts = ToastStack(content, theme_manager)
        # A click on the page takes the focus off a button, and its ring with it.
        content.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._content = content

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(content, stretch=1)
        self._central_layout = layout
        self._help_panel: HelpPanel | None = None  # built the first time it opens
        self.setCentralWidget(central)

        self.sidebar.page_requested.connect(self.show_page)
        self.sidebar.account_requested.connect(lambda i: self.show_detail(DetailId.ACCOUNT, i))
        self.top_bar.add_transaction_requested.connect(self.open_new_transaction)
        self.top_bar.help_requested.connect(self.toggle_help)
        QShortcut(QKeySequence(HELP.label), self, self.toggle_help)
        QShortcut(QKeySequence(UNDO.label), self, self.undo_last)
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
            event_bus.backups_changed,
            event_bus.goals_changed,
        ):
            signal.connect(self.refresh_notifications)
        event_bus.accounts_changed.connect(self._offer_tour_soon)
        self.show_page(PageId.DASHBOARD)
        self.refresh_notifications()

    def toast(
        self,
        text: str,
        action_text: str | None = None,
        on_action: Callable[[], object] | None = None,
    ) -> None:
        """Tells what just happened at the bottom right of the page (``ToastStack``)."""
        self.toasts.show_toast(text, action_text, on_action)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Opens with the focus on the page, not on the first button of the sidebar,
        whose focus ring is for the keyboard."""
        super().showEvent(event)
        if self.focusWidget() is None or isinstance(self.focusWidget(), QPushButton):
            self._content.setFocus()

    def undo_last(self) -> None:
        """Ctrl+Z: undoes the last action that offered «Deshacer». A text field takes
        Ctrl+Z for its own text first. Every page refreshes, since it may be any action."""
        undo(self, self._services, None, *self._event_bus.data_signals())

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
        self._rate_updater.updated.connect(lambda rates: self.toast(updated_text(rates)))
        self._rate_updater.update()

    def show_unseen_news(self) -> None:
        """After an update, tells once what changed since the version opened last.

        Called by the app once the window is open, like ``check_for_updates``."""
        entries = self._services.news.take_unseen()
        if entries:
            NewsDialog.for_entries(entries, parent=self).exec()
        self.offer_tour()

    @property
    def help_panel(self) -> HelpPanel:
        """Ayuda, beside the page; built and wired the first time it is asked for."""
        if self._help_panel is None:
            panel = HelpPanel(self.theme_manager)
            panel.hide()
            self._central_layout.addWidget(panel)
            panel.page_requested.connect(self.show_page)
            panel.spotlight_changed.connect(self.sidebar.spotlight)
            panel.tour_requested.connect(self._tour_from_help)
            # The panel had the focus; Qt would hand it to the sidebar's first button.
            panel.closed.connect(self._content.setFocus)
            self._help_panel = panel
        return self._help_panel

    def toggle_help(self) -> None:
        """F1, the «?» of the top bar and Ajustes open Ayuda, or close it when open."""
        if self.help_panel.isVisible():
            self.help_panel.close_panel()
        else:
            self.show_help()

    def show_help(self, topic: HelpTopic | None = None) -> None:
        """Opens Ayuda on ``topic``, or on the topic of the page shown: the help about
        where the user is, with that page lit up in the sidebar."""
        panel = self.help_panel
        panel.search_input.clear()
        topic = topic or topic_for_page(self.current_page_id)
        if topic is None:
            panel.show_index()
        else:
            panel.show_topic(topic)
        panel.show()
        panel.setFocus()

    @property
    def current_page_id(self) -> PageId:
        """The sidebar's page of what is shown; a detail counts as its list."""
        shown = self._stack.currentWidget()
        for page_id, page in self._pages.items():
            if page is shown:
                return page_id
        return next(d.list_page for d, page in self._details.items() if page is shown)

    def _tour_from_help(self) -> None:
        """The tour points at the whole window, so the help makes way."""
        self.help_panel.close_panel()
        self.start_tour()

    def _offer_tour_soon(self) -> None:
        """After the first account, once the form that created it has closed."""
        if self._services.tour.tour_due():
            QTimer.singleShot(0, self, self.offer_tour)

    def offer_tour(self) -> None:
        """Offers the guided tour, once: see ``TourService.tour_due``."""
        tour = self._services.tour
        if not tour.tour_due():
            return
        tour.mark_tour_offered()
        if ask(
            self,
            "Recorrido guiado",
            "¿Te muestro cómo se usa Nodus? Es un minuto.",
            TOUR_LABEL,
            "Ahora no",
        ):
            self.start_tour()

    def start_tour(self) -> CoachMarks:
        """Shows Inicio and walks over it; also opened from Ayuda and Ajustes."""
        self.show_page(PageId.DASHBOARD)
        self.tour = CoachMarks(self, TOUR_STEPS, self.theme_manager.theme)
        self.tour.start()
        return self.tour

    def _show_release(self, release: Release | None) -> None:
        self._services.notifications.set_release(release)
        self.refresh_notifications()

    # Notifications

    @property
    def _release(self) -> Release | None:
        return self._services.notifications.release

    def notices(self) -> list[Notice]:
        return self._services.notifications.notices(date.today())

    def refresh_notifications(self) -> None:
        """Updates the count on the bell, which counts only what the user has not opened
        yet, and the panel if it is open."""
        notices = self.notices()
        self.top_bar.set_notification_count(sum(1 for notice in notices if not notice.seen))
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

    @property
    def services(self) -> Services:
        return self._services

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def release(self) -> Release | None:
        """The newer version found, if any."""
        return self._release

    def _act_on_notice(self, notice: Notice) -> None:
        """Opening a notice marks it seen and leads where its problem shows (``NOTICES``);
        the bell is refreshed once, after both."""
        self._services.notifications.mark_seen(notice)
        NOTICES[notice.kind].open(self, notice)
        self.refresh_notifications()

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

    def _dismiss_notice(self, notice: Notice) -> None:
        """Puts the notice away as its kind does; a kind that cannot be is left alone."""
        dismiss = NOTICES[notice.kind].dismiss
        if dismiss is not None:
            dismiss(self, notice)
            self.refresh_notifications()

    @property
    def current_page(self) -> Page:
        return self._stack.currentWidget()

    def page(self, page_id: PageId) -> Page:
        """The page ``page_id``, built, wired and filled the first time it is asked for."""
        if page_id not in self._pages:
            page = self._build_page(page_id)
            self._pages[page_id] = page
            self._stack.addWidget(page)
            page.refresh()
        return self._pages[page_id]

    def _build_page(self, page_id: PageId) -> Page:
        """A new page ``page_id`` with its requests connected to the window."""
        services, bus, theme = self._services, self._event_bus, self.theme_manager
        if page_id is PageId.DASHBOARD:
            page = DashboardPage(services, bus, theme)
            page.budgets_requested.connect(self.show_budgets)
        elif page_id is PageId.ACCOUNTS:
            page = AccountsPage(services, bus, theme)
            page.detail_requested.connect(lambda i: self.show_detail(DetailId.ACCOUNT, i))
        elif page_id is PageId.TRANSACTIONS:
            page = TransactionsPage(services, bus, theme)
            page.new_transaction_requested.connect(self.open_new_transaction)
        elif page_id is PageId.RECURRING:
            page = RecurringPage(services, bus, theme)
        elif page_id is PageId.BUDGETS:
            page = BudgetsPage(services, bus, theme)
        elif page_id is PageId.GOALS:
            page = GoalsPage(services, bus, theme)
            page.detail_requested.connect(lambda i: self.show_detail(DetailId.GOAL, i))
        elif page_id is PageId.ANALYSIS:
            page = AnalysisPage(services, bus, theme)
        elif page_id is PageId.CATEGORIES:
            page = CategoriesPage(services, bus)
        elif page_id is PageId.PAYEES:
            page = PayeesPage(services, bus, theme)
            page.detail_requested.connect(lambda i: self.show_detail(DetailId.PAYEE, i))
        elif page_id is PageId.TAGS:
            page = TagsPage(services, bus, theme)
            page.detail_requested.connect(lambda i: self.show_detail(DetailId.TAG, i))
        else:
            page = SettingsPage(services, bus, theme)
            page.tour_requested.connect(self.start_tour)
            page.help_requested.connect(self.toggle_help)
        # The requests pages share, where a page has them.
        for name, slot in (
            ("navigate_requested", self.show_page),
            ("transactions_requested", self.show_transactions),
        ):
            signal = getattr(page, name, None)
            if signal is not None:
                signal.connect(slot)
        return page

    def show_page(self, page_id: PageId) -> None:
        built = page_id in self._pages
        page = self.page(page_id)
        if built:  # a page just built was filled already
            page.refresh()
        self._stack.setCurrentWidget(page)
        self.sidebar.select(page_id)

    def detail(self, detail_id: DetailId) -> DetailPage:
        """The detail page ``detail_id``, built and wired the first time it is asked for."""
        if detail_id not in self._details:
            services, bus, theme = self._services, self._event_bus, self.theme_manager
            if detail_id is DetailId.ACCOUNT:
                detail = AccountDetailPage(services, bus, theme)
                detail.goal_requested.connect(lambda i: self.show_detail(DetailId.GOAL, i))
            elif detail_id is DetailId.PAYEE:
                detail = PayeeDetailPage(services, bus, theme)
            elif detail_id is DetailId.TAG:
                detail = TagDetailPage(services, bus, theme)
            else:
                detail = GoalDetailPage(services, bus, theme)
                detail.account_requested.connect(lambda i: self.show_detail(DetailId.ACCOUNT, i))
            detail.back_requested.connect(partial(self.show_page, detail_id.list_page))
            detail.new_transaction_requested.connect(self.open_new_transaction)
            self._details[detail_id] = detail
            self._stack.addWidget(detail)
        return self._details[detail_id]

    def show_detail(self, detail_id: DetailId, item_id: int) -> None:
        """Opens the page about one item, with its list page selected in the sidebar."""
        page = self.detail(detail_id)
        page.show_item(item_id)
        self._stack.setCurrentWidget(page)
        self.sidebar.select(detail_id.list_page)
        page.setFocus()

    def show_transactions(self, focus: TransactionFocus) -> None:
        """Opens the transactions page on what ``focus`` asks for."""
        self.page(PageId.TRANSACTIONS).focus(focus)
        self.show_page(PageId.TRANSACTIONS)

    def show_budgets(self, month: Month) -> None:
        """Opens the budgets page on ``month``."""
        self.page(PageId.BUDGETS).show_month(month)
        self.show_page(PageId.BUDGETS)

    def open_new_transaction(self, start: TransactionStart | None = None) -> None:
        """Opens the transaction dialog, filled with what ``start`` knows, or leads to
        Cuentas when there is nowhere to record it."""
        if not self._services.accounts.list_accounts():
            QMessageBox.information(
                self,
                "Primero, una cuenta",
                "Para registrar transacciones necesitas al menos una cuenta activa."
                " Crea una en Cuentas y vuelve a intentarlo.",
            )
            self.show_page(PageId.ACCOUNTS)
            return
        dialog = TransactionDialog(
            self._services, self._event_bus, self.theme_manager, parent=self, start=start
        )
        if dialog.exec():
            self.toast("Transacción guardada.")
