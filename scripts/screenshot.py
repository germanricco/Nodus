"""Renders every page of Nodus, in light and dark themes, to PNG files.

Used to review the interface without opening it and to produce README images. It runs
over a temporary database (optionally filled with demo data), never over real user data.

    .venv/Scripts/python scripts/screenshot.py --demo --out screenshots
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import use_offscreen_qt  # noqa: E402

use_offscreen_qt()

from demo_data import load_demo_data  # noqa: E402
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QScrollArea, QWidget  # noqa: E402

from nodus import APP_NAME  # noqa: E402
from nodus.config.paths import AppPaths  # noqa: E402
from nodus.database.database import Database  # noqa: E402
from nodus.i18n import Language, _, install  # noqa: E402
from nodus.models.currency import Currency  # noqa: E402
from nodus.models.money import Money  # noqa: E402
from nodus.models.period import Month  # noqa: E402
from nodus.models.transaction import Transaction, TransactionType  # noqa: E402
from nodus.models.transaction_filter import TransactionFilter  # noqa: E402
from nodus.services.backups.recovery import RecoveryCopy  # noqa: E402
from nodus.services.container import Services  # noqa: E402
from nodus.services.external.update_service import Installer, Release  # noqa: E402
from nodus.services.transactions.transaction_service import TransactionDraft  # noqa: E402
from nodus.ui.dialogs.account_dialog import AccountDialog  # noqa: E402
from nodus.ui.dialogs.budget_dialog import BudgetDialog  # noqa: E402
from nodus.ui.dialogs.bulk_edit_dialog import BulkEditDialog  # noqa: E402
from nodus.ui.dialogs.category_dialog import CategoryDialog  # noqa: E402
from nodus.ui.dialogs.goal_dialog import GoalDialog  # noqa: E402
from nodus.ui.dialogs.recovery_dialog import DAMAGED, RESTORE, recovery_text  # noqa: E402
from nodus.ui.dialogs.refund_extra_dialog import RefundExtraDialog  # noqa: E402
from nodus.ui.dialogs.refund_picker import RefundPickerDialog  # noqa: E402
from nodus.ui.dialogs.transaction_dialog import TRANSFER_MODE, TransactionDialog  # noqa: E402
from nodus.ui.dialogs.update_dialog import UpdateDialog  # noqa: E402
from nodus.ui.dialogs.user_error import UnexpectedErrorDialog, UserErrorDialog  # noqa: E402
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog  # noqa: E402
from nodus.ui.event_bus import EventBus  # noqa: E402
from nodus.ui.navigation import DetailId, PageId  # noqa: E402
from nodus.ui.pages.accounts_page import AccountRow  # noqa: E402
from nodus.ui.qt_language import QtLanguage  # noqa: E402
from nodus.ui.shell.main_window import MainWindow  # noqa: E402
from nodus.ui.shell.tour import ADD_TRANSACTION  # noqa: E402
from nodus.ui.text.help_texts import TOPICS_BY_KEY  # noqa: E402
from nodus.ui.theme.design import set_reduced_motion  # noqa: E402
from nodus.ui.theme.theme import ThemeMode  # noqa: E402
from nodus.ui.theme.theme_manager import ThemeManager  # noqa: E402
from nodus.ui.widgets.tables.row_actions import build_menu  # noqa: E402

# Dialogs to capture, built over the demo data: name -> factory(services, event_bus, window).
DIALOGS = {
    "account-dialog": lambda services, event_bus, window: AccountDialog(
        services, event_bus, parent=window
    ),
    "category-dialog": lambda services, event_bus, window: CategoryDialog(
        services, event_bus, parent=window
    ),
    "transaction-dialog": lambda services, event_bus, window: TransactionDialog(
        services, event_bus, window.theme_manager, parent=window
    ),
    "transaction-dialog-errors": lambda services, event_bus, window: errors_dialog(
        services, event_bus, window
    ),
    "transaction-dialog-installments": lambda services, event_bus, window: installments_dialog(
        services, event_bus, window
    ),
    "transfer-dialog": lambda services, event_bus, window: transfer_dialog(
        services, event_bus, window
    ),
    "goal-dialog": lambda services, event_bus, window: goal_dialog(services, event_bus, window),
    "budget-dialog": lambda services, event_bus, window: BudgetDialog(
        services, event_bus, Month.of(date.today()), parent=window
    ),
    "transaction-dialog-refund": lambda services, event_bus, window: refund_dialog(
        services, event_bus, window
    ),
    "refund-extra-dialog": lambda services, event_bus, window: refund_extra_dialog(
        services, window
    ),
    "refund-picker": lambda services, event_bus, window: RefundPickerDialog(
        services, window.theme_manager, parent=window
    ),
    "value-adjustment-dialog": lambda services, event_bus, window: value_dialog(
        services, event_bus, window
    ),
    "bulk-edit-dialog": lambda services, event_bus, window: bulk_edit_dialog(
        services, event_bus, window
    ),
}


def bulk_edit_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """Three of the latest expenses, as when several rows are chosen."""
    expenses = [
        t
        for t in services.transactions.list_transactions(TransactionFilter())
        if t.type is TransactionType.EXPENSE and not t.is_transfer
    ][:3]
    return BulkEditDialog(services, event_bus, expenses, parent=window)


def value_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """The demo investment, with a new value typed in."""
    account = next(a for a in services.accounts.list_accounts() if a.type.changes_value
                   and a.currency.value == "ARS")  # fmt: skip
    dialog = ValueAdjustmentDialog(services, event_bus, account, parent=window)
    balance = services.accounts.balance(account.id)
    dialog.value_input.set_money(balance + Money(balance.cents // 50, balance.currency))
    return dialog


def refund_extra_dialog(services: Services, window: QWidget) -> QWidget:
    """A friend sends $ 2 more than what was left of the demo refunded purchase."""
    refund = demo_refund(services)
    left = services.refunds.summary(refund.refund_of_id).remaining
    excess = Money.from_decimal(2, left.currency)
    draft = TransactionDraft(
        account_id=refund.account_id,
        type=TransactionType.INCOME,
        amount=left + excess,
        occurred_on=date.today(),
        category_id=refund.category_id,
        refund_of_id=refund.refund_of_id,
    )
    return RefundExtraDialog(services, draft, excess, parent=window)


def demo_refund(services: Services) -> Transaction:
    """The demo refund of a purchase from the trip: its expense is from another month,
    and it has a tag."""
    refunds = services.transactions.list_transactions(
        TransactionFilter(type=TransactionType.INCOME, refund_linked=True)
    )
    tags = services.transactions.tags_for([refund.id for refund in refunds])
    return next(refund for refund in refunds if refund.id in tags)


def refund_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """The demo refund (``demo_refund``), open for editing."""
    refund = demo_refund(services)
    return TransactionDialog(services, event_bus, window.theme_manager, refund, parent=window)


def installments_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """The demo purchase in installments, open for editing: total, count and first one."""
    installment = next(
        t for t in services.transactions.list_transactions(TransactionFilter()) if t.installment
    )
    return TransactionDialog(services, event_bus, window.theme_manager, installment, parent=window)


def errors_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """A new expense saved with nothing typed: each missing field says so under itself."""
    dialog = TransactionDialog(services, event_bus, window.theme_manager, parent=window)
    dialog.save_button.click()
    return dialog


def goal_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """The demo trip open for editing: its account, what it adds and what it takes."""
    goal = services.goals.list_goals()[0]
    return GoalDialog(services, event_bus, goal, parent=window)


def transfer_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """A transfer from pesos to dollars, to show the implied exchange rate."""
    dialog = TransactionDialog(services, event_bus, window.theme_manager, parent=window)
    dialog.mode_input.set_index(TRANSFER_MODE)
    dialog.account_input.setCurrentIndex(dialog.account_input.findText("Banco"))
    dialog.amount_input.line_edit.setText("121.550")
    dialog.to_account_input.setCurrentIndex(dialog.to_account_input.findText("Ahorro en dólares"))
    dialog.amount_in_input.line_edit.setText("100")
    return dialog


# Tall enough for every dashboard card at once.
FULL_DASHBOARD_HEIGHT = 1180
FULL_SETTINGS_HEIGHT = 1500


# Turns of the event loop before each capture, so the layout has settled.
SETTLE_PASSES = 5


# File names of the analysis tabs, in their order.
ANALYSIS_TABS = ("trends", "cash-flow", "net-worth")


@dataclass
class Shots:
    """What every capture needs: the app, the window over its data, where the pictures go,
    the theme they are taken in and the window's usual height."""

    app: QApplication
    services: Services
    event_bus: EventBus
    window: MainWindow
    out: Path
    height: int
    mode: ThemeMode = ThemeMode.LIGHT

    def save(self, widget: QWidget, name: str) -> None:
        """Saves ``widget`` as ``<name>-<theme>.png``."""
        save(widget, self.out / f"{name}-{self.mode.value}.png")

    def settle(self) -> None:
        """Lets Qt lay out and paint what just changed."""
        self.app.processEvents()


def render_pages(app: QApplication, services: Services, args: argparse.Namespace) -> None:
    if args.demo:
        load_demo_data(services, args.today)
    # The tour's offer is a question that waits for an answer; «tour» captures the tour.
    services.settings.set_tour_offered(True)
    theme_manager = ThemeManager(app, ThemeMode.LIGHT)
    event_bus = EventBus()
    window = MainWindow(services, event_bus, theme_manager)
    window.show()
    shots = Shots(app, services, event_bus, window, args.out, window.height())
    for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
        theme_manager.set_mode(mode)
        shots.mode = mode
        for capture in CAPTURES:
            capture(shots)
    window.close()


def capture_pages(shots: Shots) -> None:
    """Every page, as it opens."""
    window = shots.window
    for page_id in PageId:
        window.show_page(page_id)
        shots.settle()
        shots.save(window, page_id.name.lower())


def capture_tour_and_help(shots: Shots) -> None:
    """The guided tour, and Ayuda with its topics and shortcuts."""
    window = shots.window
    # The guided tour on «Agregar transacción», as the READMEs describe it.
    tour = window.start_tour()
    while tour.steps[tour.index].target != ADD_TRANSACTION:
        tour.next()
    shots.save(window, "tour")
    tour.finish()
    # Ayuda at the side, on Metas from Inicio (Metas lit up in the sidebar), its
    # topics and its shortcuts.
    window.show_page(PageId.DASHBOARD)
    window.show_help(TOPICS_BY_KEY["goals"])
    shots.save(window, "help")
    window.help_panel.show_index()
    shots.save(window, "help-topics")
    window.help_panel.show_shortcuts()
    shots.save(window, "help-shortcuts")
    window.help_panel.close_panel()


def capture_toasts(shots: Shots) -> None:
    """Toasts on Recurrentes."""
    window = shots.window
    # Toasts on Recurrentes: one that just tells, and one with «Deshacer».
    window.show_page(PageId.RECURRING)
    window.toast("Copia guardada.")
    window.toast("Se omitió Internet.", "Deshacer", lambda: None)
    shots.save(window, "toast")
    for toast in list(window.toasts.toasts):
        toast.dismiss()


def capture_moments(shots: Shots) -> None:
    """Undoing, a charge seen, an empty group and a form left with changes."""
    window = shots.window
    services = shots.services
    capture_undo(shots.app, window, shots.out, shots.mode)
    capture_seen(shots.app, window, shots.out, shots.mode)
    capture_empty_group(shots.app, window, shots.out, shots.mode)
    capture_discard(shots.app, services, shots.event_bus, window, shots.out, shots.mode)


def capture_dialogs(shots: Shots) -> None:
    """Each form of ``DIALOGS``, the popups and the color wheel."""
    window = shots.window
    services = shots.services
    for name, build_dialog in DIALOGS.items():
        dialog = build_dialog(services, shots.event_bus, window)
        dialog.show()
        shots.settle()
        shots.save(dialog, name)
        discard(dialog)
    capture_popups(shots.app, services, shots.event_bus, window, shots.out, shots.mode)
    # The color wheel, opened from the category dialog's «+» swatch.
    dialog = CategoryDialog(services, shots.event_bus, parent=window)
    dialog.show()
    dialog.color_input.open_wheel()
    dialog.color_input.wheel_popup.set_color("#2a9d8f")
    shots.settle()
    shots.save(dialog.color_input.wheel_popup, "color-wheel")
    discard(dialog)


def capture_whole_pages(shots: Shots) -> None:
    """Inicio and Recurrentes whole. The window stays that tall until the analysis is captured."""
    window = shots.window
    # The whole dashboard, below the fold too.
    window.resize(window.width(), FULL_DASHBOARD_HEIGHT)
    window.show_page(PageId.DASHBOARD)
    shots.settle()
    shots.save(window, "dashboard-full")
    # Recurrentes, whole: the purchases in installments come after the charges.
    window.show_page(PageId.RECURRING)
    shots.settle()
    shots.save(window, "recurring-full")


def capture_details(shots: Shots) -> None:
    """The pages of one record, in the usual and the narrowest window."""
    window = shots.window
    services = shots.services
    # The page of one account: the demo investment, with its value updates.
    investment = next(
        a
        for a in services.accounts.list_accounts()
        if a.type.changes_value and a.currency is Currency.ARS
    )
    window.show_detail(DetailId.ACCOUNT, investment.id)
    shots.settle()
    shots.save(window, "account-detail")
    # The sidebar with a group folded down to its total, on the page of groups.
    banks = services.account_groups.list_groups()[0]
    window.sidebar.toggle_group(banks.id)
    window.show_page(PageId.ACCOUNTS)
    shots.settle()
    shots.save(window, "accounts-groups")
    window.sidebar.toggle_group(banks.id)
    # The page of one goal: the trip, filled by the dollar savings, on track.
    window.show_detail(DetailId.GOAL, services.goals.list_goals()[0].id)
    shots.settle()
    shots.save(window, "goal-detail")
    # The same page in the narrowest window: the figures wrap instead of being cut.
    wide = window.size()
    window.resize(window.minimumWidth(), wide.height())
    shots.settle()
    shots.save(window, "goal-detail-narrow")
    window.show_detail(DetailId.ACCOUNT, services.goals.list_goals()[0].shares[0].account_id)
    shots.settle()
    shots.save(window, "account-detail-narrow")
    window.resize(wide)
    shots.settle()
    # The card with the purchase in installments: what is still to pay.
    card = next(a for a in services.accounts.list_accounts() if a.name == "Visa")
    window.show_detail(DetailId.ACCOUNT, card.id)
    shots.settle()
    shots.save(window, "card-detail")
    # The page of the most used payee.
    payee = services.payees.summaries()[0].payee
    window.show_detail(DetailId.PAYEE, payee.id)
    shots.settle()
    shots.save(window, "payee-detail")


def capture_empty_searches(shots: Shots) -> None:
    """Searches that match nothing."""
    window = shots.window
    # Empty states: a search that matches nothing offers to clear it.
    for page_id in (PageId.TRANSACTIONS, PageId.PAYEES):
        window.show_page(page_id)
        window.page(page_id).search_input.setText("zzz")
        shots.settle()
        shots.save(window, f"{page_id.name.lower()}-empty")
        window.page(page_id).search_input.clear()


def capture_settings_and_analysis(shots: Shots) -> None:
    """Ajustes and each analysis report, whole; then the window goes back to its height."""
    window = shots.window
    # Settings, whole: the data and about cards are below the fold.
    window.resize(window.width(), FULL_SETTINGS_HEIGHT)
    window.show_page(PageId.SETTINGS)
    shots.settle()
    shots.save(window, "settings-full")
    window.resize(window.width(), FULL_DASHBOARD_HEIGHT)
    # Each analysis report, whole.
    window.show_page(PageId.ANALYSIS)
    analysis = window.page(PageId.ANALYSIS)
    for index, name in enumerate(ANALYSIS_TABS):
        analysis.tabs.set_index(index)
        # A table that grows to fit its rows resizes its card on a second pass.
        shots.settle()
        shots.settle()
        shots.save(window, f"analysis-{name}")
    analysis.tabs.set_index(0)
    window.resize(window.width(), shots.height)


def capture_controls(shots: Shots) -> None:
    """The sidebar folded, amounts hidden and the category filter open."""
    window = shots.window
    # The sidebar collapsed to its icons.
    window.sidebar.set_collapsed(True)
    shots.settle()
    shots.save(window, "sidebar-collapsed")
    window.sidebar.set_collapsed(False)
    # Balances and the net worth hidden with the eye.
    window.show_page(PageId.DASHBOARD)
    window.toggle_amounts_hidden()
    shots.settle()
    shots.save(window, "amounts-hidden")
    window.toggle_amounts_hidden()
    # The category filter open, with its expense and income sections.
    window.show_page(PageId.TRANSACTIONS)
    category_filter = window.page(PageId.TRANSACTIONS).category_filter
    category_filter.showPopup()
    shots.settle()
    shots.save(category_filter.view().window(), "category-filter")
    # Its end, with the «Editar» row that leads to Categorías.
    category_filter.view().scrollToBottom()
    shots.settle()
    shots.save(category_filter.view().window(), "category-filter-end")
    category_filter.hidePopup()


def capture_rows(shots: Shots) -> None:
    """A row's menu, a row under the mouse and a selection."""
    window = shots.window
    # A row's «⋯» menu, on an investment account, which offers every kind of action.
    window.show_page(PageId.ACCOUNTS)
    shots.settle()
    accounts = window.page(PageId.ACCOUNTS)
    # Rebuilt lists leave hidden rows waiting to be deleted; only a shown one counts.
    row = next(r for r in accounts.findChildren(AccountRow) if r.isVisible() and r.can_update_value)
    row.more_button.open_menu()
    shots.settle()
    shots.save(row.more_button.menu, "row-menu")
    row.more_button.menu.close()
    # A row lights up under the mouse.
    # Offscreen there is no real pointer, so the row is told it is under the mouse.
    row.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)
    row.repaint()
    shots.save(window, "accounts-hover")
    row.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
    # Several transactions chosen: the selection bar takes the header.
    window.show_page(PageId.TRANSACTIONS)
    transactions = window.page(PageId.TRANSACTIONS)
    for row in (1, 2, 3):
        transactions.table.toggle_row(row)
    transactions.table.hovered_row = 5  # under the mouse, not chosen
    shots.settle()
    shots.save(window, "transactions-selection")
    transactions.table.clearSelection()
    transactions.table.hovered_row = -1


def capture_messages(shots: Shots) -> None:
    """The notifications, an update on its way and an error."""
    window = shots.window
    services = shots.services
    # The notifications panel, with a new version announced and the last notice
    # already opened, gray and without its dot.
    window.show_page(PageId.DASHBOARD)
    news = Release("9.9.0", "")
    window._show_release(news)
    notices = window.notices()
    services.notifications.mark_seen(notices[-1])
    window.open_notifications()
    shots.settle()
    shots.save(window.notification_panel, "notifications")
    window.notification_panel.hide()
    services.settings.set_seen_notices(set())
    window._show_release(None)
    # Updating from Nodus, halfway through the download (never started: no network).
    size = 24_578_342
    release = Release("9.9.0", "", installer=Installer("", size, ""))
    update = UpdateDialog(services.updates, release, parent=window)
    update.progressed.emit(size // 2)
    update.show()
    shots.settle()
    shots.save(update, "update-dialog")
    update.close()
    # An error that says what to do, with the system's text unfolded.
    error = UserErrorDialog(
        "Copia fuera de la PC",
        "No se pudo guardar la copia.",
        r"Revisa que la carpeta E:\Nodus exista y que el pendrive o el disco sigan"
        " conectados y con lugar libre. Después vuelve a intentarlo.",
        r"[Errno 28] No space left on device: 'E:\Nodus\nodus-2026-11-14.db'",
        parent=window,
    )
    error.detail.toggle()
    error.show()
    shots.settle()
    shots.save(error, "user-error")
    error.close()
    # A fault of Nodus, with «Enviar reporte» and the folder of the log.
    try:
        raise KeyError("category_id")
    except KeyError as fault:
        unexpected = UnexpectedErrorDialog(fault, Path("C:/Nodus/logs"), parent=window)
    unexpected.show()
    shots.settle()
    shots.save(unexpected, "unexpected-error")
    unexpected.close()
    # The data file damaged: the newest whole copy, offered before any window.
    copy = RecoveryCopy(Path("nodus-2026-11-16.db"), datetime(2026, 11, 16, 9, 30))
    recovery = UserErrorDialog(
        APP_NAME, _(DAMAGED), recovery_text(copy), "file is not a database", action=_(RESTORE)
    )
    recovery.show()
    shots.settle()
    shots.save(recovery, "recovery-dialog")
    recovery.close()


# In order: some leave the window as the next one expects it (taller, on a page).
CAPTURES = [
    capture_pages,
    capture_tour_and_help,
    capture_toasts,
    capture_moments,
    capture_dialogs,
    capture_whole_pages,
    capture_details,
    capture_empty_searches,
    capture_settings_and_analysis,
    capture_controls,
    capture_rows,
    capture_messages,
]


def capture_popups(
    app: QApplication,
    services: Services,
    event_bus: EventBus,
    window: QWidget,
    out: Path,
    mode: ThemeMode,
) -> None:
    """The lists and menus that open over a page, open: «Cuotas», «Categoría», the
    payee suggestions and the calendar of the transaction form, the type and category
    filters of Transacciones and a row's «⋯» menu. They are the windows offscreen
    captures miss otherwise, and they share the Popup spacing."""
    dialog = TransactionDialog(services, event_bus, window.theme_manager, parent=window)
    dialog.show()
    app.processEvents()
    for name, combo in (
        ("popup-installments", dialog.installment_fields.count_input),
        ("popup-category", dialog.category_input),
    ):
        combo.showPopup()
        app.processEvents()
        save(combo.view().window(), out / f"{name}-{mode.value}.png")
        combo.hidePopup()
    # What an empty «Beneficiario» offers when clicked: the payees used most lately.
    payee = dialog.payee_input
    payee.names.suggest("")
    app.processEvents()
    popup = payee.completer.popup()
    if popup.isVisible():
        save(popup, out / f"popup-payee-{mode.value}.png")
        popup.hide()
    field = dialog.date_input
    field.open_calendar()
    app.processEvents()
    calendar = field.calendarWidget()
    if calendar.isVisible():
        save(calendar.window(), out / f"popup-calendar-{mode.value}.png")
        calendar.window().hide()
    discard(dialog)
    window.show_page(PageId.TRANSACTIONS)
    page = window.page(PageId.TRANSACTIONS)
    for name, combo in (
        ("popup-filter", page.type_filter),
        ("popup-category-filter", page.category_filter),
    ):
        combo.showPopup()
        app.processEvents()
        save(combo.view().window(), out / f"{name}-{mode.value}.png")
        combo.hidePopup()
    menu = build_menu(window, page.list_view.row_actions(0))
    menu.popup(window.mapToGlobal(window.rect().center()))
    app.processEvents()
    save(menu, out / f"popup-menu-{mode.value}.png")
    menu.close()


def capture_undo(app: QApplication, window: MainWindow, out: Path, mode: ThemeMode) -> None:
    """A real «Omitir» on Recurrentes and the notice that offers to undo it; undone
    after, so the next captures show the demo data as it was."""
    page = window.page(PageId.RECURRING)
    skip = next(action for action in page.rows[0].actions() if action.text == _("Omitir"))
    skip.callback()
    app.processEvents()
    save(window, out / f"toast-undo-{mode.value}.png")
    window.undo_last()
    for toast in list(window.toasts.toasts):
        toast.dismiss()


def capture_seen(app: QApplication, window: MainWindow, out: Path, mode: ThemeMode) -> None:
    """«Ya lo vi» on the first upcoming payment of Inicio: its pill gray and the notice
    with the day it warns again; put back after, for the next captures."""
    window.show_page(PageId.DASHBOARD)
    row = window.page(PageId.DASHBOARD).upcoming_card.rows[1]  # due in 2 days
    charge = row.charge
    seen = next(action for action in row.actions() if action.text == _("Ya lo vi"))
    seen.callback()
    app.processEvents()
    save(window, out / f"upcoming-seen-{mode.value}.png")
    window._services.recurring.remind_again(charge.id, date.today())
    window._event_bus.recurring_changed.emit()
    for toast in list(window.toasts.toasts):
        toast.dismiss()


def capture_empty_group(app: QApplication, window: MainWindow, out: Path, mode: ThemeMode) -> None:
    """Cuentas with an empty group: where an account can be dragged. Deleted after."""
    services = window._services
    group = services.account_groups.create("Para más adelante")
    window._event_bus.accounts_changed.emit()
    window.show_page(PageId.ACCOUNTS)
    page = window.page(PageId.ACCOUNTS)
    app.processEvents()
    zone = page.account_lists[group.id].placeholder
    page.findChild(QScrollArea).ensureWidgetVisible(zone)
    app.processEvents()
    save(window, out / f"accounts-empty-group-{mode.value}.png")
    services.account_groups.delete(group.id)
    window._event_bus.accounts_changed.emit()


def capture_discard(
    app: QApplication,
    services: Services,
    event_bus: EventBus,
    window: MainWindow,
    out: Path,
    mode: ThemeMode,
) -> None:
    """«¿Descartar los cambios?» over a category form with a name typed. The question
    waits for an answer, so a timer captures it and answers «Seguir editando»."""
    dialog = CategoryDialog(services, event_bus, parent=window)
    dialog.show()
    app.processEvents()
    dialog.name_input.setText("Mascotas")

    def capture_question() -> None:
        question = QApplication.activeModalWidget()
        app.processEvents()
        save(question, out / f"form-discard-{mode.value}.png")
        question.reject()

    QTimer.singleShot(0, capture_question)
    dialog.reject()
    discard(dialog)


def discard(dialog: QDialog) -> None:
    """Closes a dialog the capture filled in, without its «¿Descartar los cambios?»,
    which would wait for an answer: ``done`` skips ``reject``."""
    dialog.done(QDialog.DialogCode.Rejected)


def save(widget: QWidget, path: Path) -> None:
    # A page laid out again (another width, another height, another tab) settles over a
    # few turns of the event loop; a single one can catch it halfway, with its lists
    # crushed. The running app never stops between turns, so only a capture can.
    for _turn in range(SETTLE_PASSES):
        QApplication.processEvents()
    widget.grab().save(str(path))
    print(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("screenshots"))
    parser.add_argument("--demo", action="store_true", help="load sample accounts and movements")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--lang", choices=[language.value for language in Language], default="es")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # Charts are captured in their final state, not halfway through their transitions.
    set_reduced_motion(True)
    app = QApplication(sys.argv)
    language = Language(args.lang)
    install(language)
    qt_language = QtLanguage(app)
    qt_language.apply(language)
    with tempfile.TemporaryDirectory() as data_dir:
        paths = AppPaths(Path(data_dir))
        database = Database.open(paths.database_path)
        try:
            render_pages(app, Services.create(database, paths.backups_dir), args)
        finally:
            database.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
