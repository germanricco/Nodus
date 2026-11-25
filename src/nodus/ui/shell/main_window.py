"""Main application window."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QResizeEvent, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nodus import APP_NAME
from nodus.i18n import _
from nodus.links import feedback_url
from nodus.models.period import Month
from nodus.services.app.notification_service import Notice
from nodus.services.container import Services
from nodus.services.external.update_service import (
    RETRY_AFTER_FAILURE,
    Release,
    UpdateCheck,
)
from nodus.ui.background import BackgroundCall
from nodus.ui.browser import open_url
from nodus.ui.dialogs.confirm import ask, tell
from nodus.ui.dialogs.news_dialog import NewsDialog
from nodus.ui.dialogs.transaction_dialog import TransactionDialog, TransactionStart
from nodus.ui.dialogs.update_dialog import UpdateDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, PageId, RecordLink, TransactionFocus
from nodus.ui.pages.base.detail_page import DetailPage
from nodus.ui.pages.base.page import Page
from nodus.ui.rate_updater import shared_rate_updater, updated_text
from nodus.ui.refresh import refresh_on_changes
from nodus.ui.restart import restart
from nodus.ui.shell.coach_marks import CoachMarks
from nodus.ui.shell.command_palette import (
    ACTION,
    Command,
    CommandPalette,
    page_commands,
    record_commands,
)
from nodus.ui.shell.help_panel import HelpPanel
from nodus.ui.shell.history import NavigationHistory, Place
from nodus.ui.shell.notices import NOTICES
from nodus.ui.shell.notification_panel import NotificationPanel
from nodus.ui.shell.page_registry import DETAIL_OF_LIST, DETAIL_TYPES, PAGE_TYPES
from nodus.ui.shell.sidebar import Sidebar
from nodus.ui.shell.top_bar import TopBar
from nodus.ui.shell.tour import TOUR_STEPS
from nodus.ui.shortcuts import (
    BACK,
    COMMAND_PALETTE,
    FORWARD,
    HELP,
    HIDE_AMOUNTS,
    NEW_TRANSACTION,
    SEARCH,
    UNDO,
    page_keys,
    with_keys,
)
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
        self._checking_updates = False
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
        self._folded_for_help = False  # the sidebar folded to make room for Ayuda
        self._sidebar_by_hand = False  # folded or unfolded by the user while Ayuda is open
        self.sidebar.collapse_button.clicked.connect(self._sidebar_moved_by_hand)
        self.setCentralWidget(central)

        self.sidebar.page_requested.connect(self.show_page)
        self.sidebar.record_requested.connect(self.open_record)
        self.top_bar.add_transaction_requested.connect(self.open_new_transaction)
        self.top_bar.help_requested.connect(self.toggle_help)
        self.history = NavigationHistory()
        for shortcut, action in (
            (HELP, self.toggle_help),
            (UNDO, self.undo_last),
            (NEW_TRANSACTION, self.open_new_transaction),
            (SEARCH, self.find),
            (HIDE_AMOUNTS, self.toggle_amounts_hidden),
            (BACK, self.go_back),
            (FORWARD, self.go_forward),
            (COMMAND_PALETTE, self.open_palette),
        ):
            QShortcut(shortcut.sequence, self, action)
        for page_id, keys in page_keys().items():
            QShortcut(QKeySequence(keys), self, partial(self.show_page, page_id))
        self.top_bar.notifications_requested.connect(self.open_notifications)
        self.top_bar.feedback_requested.connect(lambda: open_url(feedback_url()))
        self.top_bar.set_amounts_hidden(services.settings.amounts_hidden())
        self.top_bar.hide_amounts_toggled.connect(self.toggle_amounts_hidden)
        self._rate_updater = shared_rate_updater(services, event_bus)
        # Whoever asked for the rates, at the start of Nodus or from Ajustes.
        self._rate_updater.updated.connect(self._announce_rates)
        refresh_on_changes(
            event_bus, theme_manager, self.refresh_screen, self._refresh_current_page
        )
        event_bus.accounts_changed.connect(self._offer_tour_soon)
        self.show_page(PageId.DASHBOARD)
        self.refresh_notifications()

    def _announce_rates(self, rates: dict) -> None:
        self.toast(updated_text(rates))

    def refresh_screen(self) -> None:
        """What a change refreshes (``refresh``): the page in view, the accounts of the
        sidebar and the bell."""
        self._refresh_current_page()
        self.sidebar.refresh_accounts()
        self.refresh_notifications()

    def _refresh_current_page(self) -> None:
        page = self._stack.currentWidget()
        if isinstance(page, Page):
            page.request_refresh()

    def toast(
        self,
        text: str,
        action_text: str | None = None,
        on_action: Callable[[], object] | None = None,
    ) -> None:
        """Tells what just happened at the bottom right of the page (``ToastStack``)."""
        self.toasts.show_toast(text, action_text, on_action)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._make_room_for_help_soon()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Opens with the focus on the page, not on the first button of the sidebar,
        whose focus ring is for the keyboard."""
        super().showEvent(event)
        if self.focusWidget() is None or isinstance(self.focusWidget(), QPushButton):
            self._content.setFocus()

    def bring_to_front(self) -> None:
        """Opening Nodus again lands here: the window comes back from the taskbar, if it
        was minimized, and to the front."""
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def undo_last(self) -> None:
        """Ctrl+Z: undoes the last action that offered «Deshacer». A text field takes
        Ctrl+Z for its own text first. Every page refreshes, since it may be any action."""
        undo(self, self._services, None, *self._event_bus.data_signals())

    def check_for_updates(self) -> None:
        """Looks for a new version in the background, unless the user turned it off, and
        again later on its own (``UpdateCheck.next_in``): soon after a failure, as when
        GitHub limits a connection shared by many, and every few hours while Nodus stays
        open. One check at a time.

        Called by the app once the window is open, not on construction, so tests and
        screenshots never reach the network."""
        if not self._services.settings.check_updates() or self._checking_updates:
            return
        self._checking_updates = True
        self._update_check = BackgroundCall(self._services.updates.check, parent=self)
        self._update_check.done.connect(self._show_release)
        # Something nobody expected went wrong (it is in the log): try again later too.
        self._update_check.failed.connect(
            lambda: self._show_release(UpdateCheck(retry_in=RETRY_AFTER_FAILURE))
        )
        self._update_check.start()

    def update_exchange_rate(self) -> None:
        """Brings today's dollar rate in the background when the source is automatic.

        Called by the app once the window is open, like ``check_for_updates``."""
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
            panel.closed.connect(self._unfold_after_help)
            self._help_panel = panel
        return self._help_panel

    def _make_room_for_help_soon(self) -> None:
        """Once the page has taken the width left beside Ayuda: see ``_make_room_for_help``."""
        QTimer.singleShot(0, self, self._make_room_for_help)

    def _make_room_for_help(self) -> None:
        """Folds the sidebar while Ayuda is open if the page shown would be cut: a page
        that never scrolls sideways and needs more width than it has. Closing Ayuda
        unfolds it again."""
        panel = self._help_panel
        if panel is None or not panel.isVisible() or self.sidebar.is_collapsed:
            return
        if self._sidebar_by_hand:  # the user's choice wins until Ayuda closes
            return
        self._central_layout.activate()  # the page takes its width now, not later
        if self._page_is_cut():
            self.sidebar.set_collapsed(True)
            self._folded_for_help = True

    def _page_is_cut(self) -> bool:
        page = self._stack.currentWidget()
        return any(
            area.widget() is not None
            and area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            and area.widget().minimumSizeHint().width() > area.viewport().width()
            for area in page.findChildren(QScrollArea)
        )

    def _unfold_after_help(self) -> None:
        if self._folded_for_help:
            self.sidebar.set_collapsed(False)
        self._folded_for_help = self._sidebar_by_hand = False

    def _sidebar_moved_by_hand(self) -> None:
        self._folded_for_help = False
        if self._help_panel is not None and self._help_panel.isVisible():
            self._sidebar_by_hand = True

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
        self._make_room_for_help_soon()

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
            _("Recorrido guiado"),
            _("¿Te muestro cómo se usa Nodus? Es un minuto."),
            _(TOUR_LABEL),
            _("Ahora no"),
        ):
            self.start_tour()

    def start_tour(self) -> CoachMarks:
        """Shows Inicio and walks over it; also opened from Ayuda and Ajustes."""
        self.show_page(PageId.DASHBOARD)
        self.tour = CoachMarks(self, TOUR_STEPS, self.theme_manager.theme)
        self.tour.start()
        return self.tour

    def _show_release(self, check: UpdateCheck) -> None:
        """Shows what the check found, and plans the next one. A failed check leaves the
        notice as it was: it found nothing, but a version found before still stands."""
        self._checking_updates = False
        if not check.failed:
            self._services.notifications.set_release(check.release)
            self.refresh_notifications()
        milliseconds = int(check.next_in.total_seconds() * 1000)
        QTimer.singleShot(milliseconds, self, self.check_for_updates)

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
        opens it again, or restarts it over the new AppImage. Run from the source code, or
        without an installer attached, the release page opens instead."""
        updates = self._services.updates
        if not updates.can_install(release):
            open_url(release.url)
            return
        dialog = UpdateDialog(updates, release, parent=self)
        dialog.exec()
        if not dialog.installing:
            return
        if updates.reopens_by_itself:
            QApplication.quit()
        else:
            restart()

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
        """A new page ``page_id`` (``PAGE_TYPES``) with its requests connected."""
        page = PAGE_TYPES[page_id](self._services, self._event_bus, self.theme_manager)
        search = page.search_input
        if search is not None:
            what = search.toolTip() or search.placeholderText().rstrip("…")
            search.setToolTip(with_keys(what, SEARCH.label))
        detail = DETAIL_OF_LIST.get(page_id)
        if detail is not None:
            page.detail_requested.connect(partial(self.show_detail, detail))
        self._connect_requests(page)
        return page

    def _connect_requests(self, page: Page) -> None:
        """Connects what a page may ask of the window, by the name of its signal: every
        page that has one asks for the same thing."""
        for name, slot in (
            ("navigate_requested", self.show_page),
            ("transactions_requested", self.show_transactions),
            ("budgets_requested", self.show_budgets),
            ("new_transaction_requested", self.open_new_transaction),
            ("tour_requested", self.start_tour),
            ("help_requested", self.toggle_help),
            ("record_requested", self.open_record),
        ):
            signal = getattr(page, name, None)
            if signal is not None:
                signal.connect(slot)

    def open_record(self, link: RecordLink) -> None:
        """The page of the record a click led to."""
        self.show_detail(link.detail, link.item_id)

    def show_page(self, page_id: PageId) -> None:
        built = page_id in self._pages
        page = self.page(page_id)
        if built:  # a page just built was filled already
            page.refresh()
        self._stack.setCurrentWidget(page)
        self.sidebar.select(page_id)
        self.history.visit(Place(page_id))
        self._make_room_for_help_soon()

    def detail(self, detail_id: DetailId) -> DetailPage:
        """The detail page ``detail_id``, built and wired the first time it is asked for."""
        if detail_id not in self._details:
            services, bus, theme = self._services, self._event_bus, self.theme_manager
            detail = DETAIL_TYPES[detail_id](services, bus, theme)
            detail.back_requested.connect(partial(self.show_page, detail_id.list_page))
            self._connect_requests(detail)
            self._details[detail_id] = detail
            self._stack.addWidget(detail)
        return self._details[detail_id]

    def show_detail(self, detail_id: DetailId, item_id: int) -> None:
        """Opens the page about one item, with its list page selected in the sidebar."""
        page = self.detail(detail_id)
        page.show_item(item_id)
        self._stack.setCurrentWidget(page)
        self.sidebar.select(detail_id.list_page)
        self.history.visit(Place(detail_id, item_id))
        self._make_room_for_help_soon()
        page.setFocus()

    def go_back(self) -> None:
        """The page shown before this one (Alt+←)."""
        self._go_to(self.history.back())

    def go_forward(self) -> None:
        """The page gone back from (Alt+→)."""
        self._go_to(self.history.forward())

    def _go_to(self, place: Place | None) -> None:
        if place is None:
            return
        with self.history.moving():
            if isinstance(place.page, DetailId) and place.item_id is not None:
                self.show_detail(place.page, place.item_id)
            elif isinstance(place.page, PageId):
                self.show_page(place.page)

    def open_palette(self) -> CommandPalette:
        """Ctrl+K: the palette over the window, with the ones chosen last first."""
        settings = self._services.settings
        palette = CommandPalette(
            [
                *page_commands(self.show_page),
                *self._action_commands(),
                *record_commands(self._services, self.open_record),
            ],
            settings.recent_commands(),
            self._run_command,
            self,
        )
        palette.open_over(self)
        return palette

    def _action_commands(self) -> list[Command]:
        """What the window does, with the keys that also do it."""
        action = _(ACTION)
        return [
            Command("action:new", _("Agregar transacción"), action, self.open_new_transaction,
                    NEW_TRANSACTION.label),
            Command("action:find", _("Buscar en Transacciones"), action, self.find, SEARCH.label),
            Command("action:amounts", _("Ocultar o mostrar los montos"), action,
                    self.toggle_amounts_hidden, HIDE_AMOUNTS.label),
            Command("action:help", _("Abrir la Ayuda"), action, self.show_help, HELP.label),
            Command("action:tour", _("Ver el recorrido"), action, self.start_tour),
            *self._repeat_commands(action),
        ]  # fmt: skip

    def _repeat_commands(self, section: str) -> list[Command]:
        """«Repetir el último gasto», with what it was, when there is one to repeat."""
        last = self._services.transactions.last_expense()
        if last is None:
            return []
        start = TransactionStart(copy_of=last)
        return [
            Command(
                "action:repeat",
                _("Repetir el último gasto"),
                section,
                lambda: self.open_new_transaction(start),
            )
        ]

    def _run_command(self, command: Command) -> None:
        self._services.settings.add_recent_command(command.key)
        command.run()

    def find(self) -> None:
        """Ctrl+F: the search of the page, or of Transacciones where the page has none,
        ready to type in."""
        search = self.current_page.search_input
        if search is None or not search.isVisibleTo(self.current_page):
            self.show_page(PageId.TRANSACTIONS)
            search = self.current_page.search_input
        if search is not None:
            search.setFocus(Qt.FocusReason.ShortcutFocusReason)
            search.selectAll()

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
            tell(
                self,
                _("Primero, una cuenta"),
                _(
                    "Para registrar transacciones necesitas al menos una cuenta activa."
                    " Crea una en Cuentas y vuelve a intentarlo."
                ),
            )
            self.show_page(PageId.ACCOUNTS)
            return
        dialog = TransactionDialog(
            self._services, self._event_bus, self.theme_manager, parent=self, start=start
        )
        if dialog.exec():
            self.toast(_("Transacción guardada."))
