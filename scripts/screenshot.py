"""Renders every page of Nodus, in light and dark themes, to PNG files.

Used to review the interface without opening it and to produce README images. It runs
over a temporary database (optionally filled with demo data), never over real user data.

    .venv/Scripts/python scripts/screenshot.py --demo --out screenshots
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The offscreen platform does not see the system fonts on Windows unless told where they are.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QScrollArea, QWidget  # noqa: E402

from nodus.database.database import Database  # noqa: E402
from nodus.models.currency import Currency  # noqa: E402
from nodus.models.money import Money  # noqa: E402
from nodus.models.period import Month  # noqa: E402
from nodus.models.transaction import TransactionType  # noqa: E402
from nodus.models.transaction_filter import TransactionFilter  # noqa: E402
from nodus.services.container import Services  # noqa: E402
from nodus.services.update_service import Installer, Release  # noqa: E402
from nodus.ui.dialogs.account_dialog import AccountDialog  # noqa: E402
from nodus.ui.dialogs.budget_dialog import BudgetDialog  # noqa: E402
from nodus.ui.dialogs.bulk_edit_dialog import BulkEditDialog  # noqa: E402
from nodus.ui.dialogs.category_dialog import CategoryDialog  # noqa: E402
from nodus.ui.dialogs.goal_dialog import GoalDialog  # noqa: E402
from nodus.ui.dialogs.refund_picker import RefundPickerDialog  # noqa: E402
from nodus.ui.dialogs.transaction_dialog import TRANSFER_MODE, TransactionDialog  # noqa: E402
from nodus.ui.dialogs.update_dialog import UpdateDialog  # noqa: E402
from nodus.ui.dialogs.user_error import UserErrorDialog  # noqa: E402
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog  # noqa: E402
from nodus.ui.event_bus import EventBus  # noqa: E402
from nodus.ui.help_texts import TOPICS_BY_KEY  # noqa: E402
from nodus.ui.main_window import MainWindow  # noqa: E402
from nodus.ui.navigation import DetailId, PageId  # noqa: E402
from nodus.ui.pages.accounts_page import AccountRow  # noqa: E402
from nodus.ui.theme.design import set_reduced_motion  # noqa: E402
from nodus.ui.theme.theme import ThemeMode  # noqa: E402
from nodus.ui.theme.theme_manager import ThemeManager  # noqa: E402
from nodus.ui.widgets.row_actions import build_menu  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from demo_data import load_demo_data  # noqa: E402

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


def refund_dialog(services: Services, event_bus: EventBus, window: QWidget) -> QWidget:
    """The demo refund of a purchase from the trip, open for editing: its expense, from
    another month, and its tag."""
    refunds = services.transactions.list_transactions(
        TransactionFilter(type=TransactionType.INCOME, refund_linked=True)
    )
    tags = services.transactions.tags_for([refund.id for refund in refunds])
    refund = next(refund for refund in refunds if refund.id in tags)
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


def render_pages(app: QApplication, services: Services, args: argparse.Namespace) -> None:
    if args.demo:
        load_demo_data(services, args.today)
    # The tour's offer is a question that waits for an answer; «tour» captures the tour.
    services.settings.set_tour_offered(True)
    theme_manager = ThemeManager(app, ThemeMode.LIGHT)
    event_bus = EventBus()
    window = MainWindow(services, event_bus, theme_manager)
    window.show()
    height = window.height()
    for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
        theme_manager.set_mode(mode)
        for page_id in PageId:
            window.show_page(page_id)
            app.processEvents()
            save(window, args.out / f"{page_id.name.lower()}-{mode.value}.png")
        # The guided tour, on its third step.
        tour = window.start_tour()
        tour.next()
        tour.next()
        save(window, args.out / f"tour-{mode.value}.png")
        tour.finish()
        # Ayuda at the side, on Metas from Inicio (Metas lit up in the sidebar), its
        # topics and its shortcuts.
        window.show_page(PageId.DASHBOARD)
        window.show_help(TOPICS_BY_KEY["goals"])
        save(window, args.out / f"help-{mode.value}.png")
        window.help_panel.show_index()
        save(window, args.out / f"help-topics-{mode.value}.png")
        window.help_panel.show_shortcuts()
        save(window, args.out / f"help-shortcuts-{mode.value}.png")
        window.help_panel.close_panel()
        # Toasts on Recurrentes: one that just tells, and one with «Deshacer».
        window.show_page(PageId.RECURRING)
        window.toast("Copia guardada.")
        window.toast("Se omitió Internet.", "Deshacer", lambda: None)
        save(window, args.out / f"toast-{mode.value}.png")
        for toast in list(window.toasts.toasts):
            toast.dismiss()
        capture_undo(app, window, args.out, mode)
        capture_seen(app, window, args.out, mode)
        capture_empty_group(app, window, args.out, mode)
        capture_discard(app, services, event_bus, window, args.out, mode)
        for name, build_dialog in DIALOGS.items():
            dialog = build_dialog(services, event_bus, window)
            dialog.show()
            app.processEvents()
            save(dialog, args.out / f"{name}-{mode.value}.png")
            discard(dialog)
        capture_popups(app, services, event_bus, window, args.out, mode)
        # The color wheel, opened from the category dialog's «+» swatch.
        dialog = CategoryDialog(services, event_bus, parent=window)
        dialog.show()
        dialog.color_input.open_wheel()
        dialog.color_input.wheel_popup.set_color("#2a9d8f")
        app.processEvents()
        save(dialog.color_input.wheel_popup, args.out / f"color-wheel-{mode.value}.png")
        discard(dialog)
        # The whole dashboard, below the fold too.
        window.resize(window.width(), FULL_DASHBOARD_HEIGHT)
        window.show_page(PageId.DASHBOARD)
        app.processEvents()
        save(window, args.out / f"dashboard-full-{mode.value}.png")
        # Recurrentes, whole: the purchases in installments come after the charges.
        window.show_page(PageId.RECURRING)
        app.processEvents()
        save(window, args.out / f"recurring-full-{mode.value}.png")
        # The page of one account: the demo investment, with its value updates.
        investment = next(
            a
            for a in services.accounts.list_accounts()
            if a.type.changes_value and a.currency is Currency.ARS
        )
        window.show_detail(DetailId.ACCOUNT, investment.id)
        app.processEvents()
        save(window, args.out / f"account-detail-{mode.value}.png")
        # The sidebar with a group folded down to its total, on the page of groups.
        banks = services.account_groups.list_groups()[0]
        window.sidebar.toggle_group(banks.id)
        window.show_page(PageId.ACCOUNTS)
        app.processEvents()
        save(window, args.out / f"accounts-groups-{mode.value}.png")
        window.sidebar.toggle_group(banks.id)
        # The page of one goal: the trip, filled by the dollar savings, on track.
        window.show_detail(DetailId.GOAL, services.goals.list_goals()[0].id)
        app.processEvents()
        save(window, args.out / f"goal-detail-{mode.value}.png")
        # The same page in the narrowest window: the figures wrap instead of being cut.
        wide = window.size()
        window.resize(window.minimumWidth(), wide.height())
        app.processEvents()
        save(window, args.out / f"goal-detail-narrow-{mode.value}.png")
        window.show_detail(DetailId.ACCOUNT, services.goals.list_goals()[0].shares[0].account_id)
        app.processEvents()
        save(window, args.out / f"account-detail-narrow-{mode.value}.png")
        window.resize(wide)
        app.processEvents()
        # The card with the purchase in installments: what is still to pay.
        card = next(a for a in services.accounts.list_accounts() if a.name == "Visa")
        window.show_detail(DetailId.ACCOUNT, card.id)
        app.processEvents()
        save(window, args.out / f"card-detail-{mode.value}.png")
        # The page of the most used payee.
        payee = services.payees.summaries()[0].payee
        window.show_detail(DetailId.PAYEE, payee.id)
        app.processEvents()
        save(window, args.out / f"payee-detail-{mode.value}.png")
        # Empty states: a search that matches nothing offers to clear it.
        for page_id in (PageId.TRANSACTIONS, PageId.PAYEES):
            window.show_page(page_id)
            window.page(page_id).search_input.setText("zzz")
            app.processEvents()
            save(window, args.out / f"{page_id.name.lower()}-empty-{mode.value}.png")
            window.page(page_id).search_input.clear()
        # Settings, whole: the data and about cards are below the fold.
        window.resize(window.width(), FULL_SETTINGS_HEIGHT)
        window.show_page(PageId.SETTINGS)
        app.processEvents()
        save(window, args.out / f"settings-full-{mode.value}.png")
        window.resize(window.width(), FULL_DASHBOARD_HEIGHT)
        # Each analysis report, whole.
        window.show_page(PageId.ANALYSIS)
        analysis = window.page(PageId.ANALYSIS)
        for index, name in enumerate(ANALYSIS_TABS):
            analysis.tabs.set_index(index)
            # A table that grows to fit its rows resizes its card on a second pass.
            app.processEvents()
            app.processEvents()
            save(window, args.out / f"analysis-{name}-{mode.value}.png")
        analysis.tabs.set_index(0)
        window.resize(window.width(), height)
        # The sidebar collapsed to its icons.
        window.sidebar.set_collapsed(True)
        app.processEvents()
        save(window, args.out / f"sidebar-collapsed-{mode.value}.png")
        window.sidebar.set_collapsed(False)
        # Balances and the net worth hidden with the eye.
        window.show_page(PageId.DASHBOARD)
        window.toggle_amounts_hidden()
        app.processEvents()
        save(window, args.out / f"amounts-hidden-{mode.value}.png")
        window.toggle_amounts_hidden()
        # The category filter open, with its expense and income sections.
        window.show_page(PageId.TRANSACTIONS)
        category_filter = window.page(PageId.TRANSACTIONS).category_filter
        category_filter.showPopup()
        app.processEvents()
        save(category_filter.view().window(), args.out / f"category-filter-{mode.value}.png")
        # Its end, with the «Editar» row that leads to Categorías.
        category_filter.view().scrollToBottom()
        app.processEvents()
        save(category_filter.view().window(), args.out / f"category-filter-end-{mode.value}.png")
        category_filter.hidePopup()
        # A row's «⋯» menu, on an investment account, which offers every kind of action.
        window.show_page(PageId.ACCOUNTS)
        app.processEvents()
        accounts = window.page(PageId.ACCOUNTS)
        # Rebuilt lists leave hidden rows waiting to be deleted; only a shown one counts.
        row = next(
            r for r in accounts.findChildren(AccountRow) if r.isVisible() and r.can_update_value
        )
        row.more_button.open_menu()
        app.processEvents()
        save(row.more_button.menu, args.out / f"row-menu-{mode.value}.png")
        row.more_button.menu.close()
        # A row lights up under the mouse.
        # Offscreen there is no real pointer, so the row is told it is under the mouse.
        row.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)
        row.repaint()
        save(window, args.out / f"accounts-hover-{mode.value}.png")
        row.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        # Several transactions chosen: the selection bar takes the header.
        window.show_page(PageId.TRANSACTIONS)
        transactions = window.page(PageId.TRANSACTIONS)
        for row in (1, 2, 3):
            transactions.table.toggle_row(row)
        transactions.table.hovered_row = 5  # under the mouse, not chosen
        app.processEvents()
        save(window, args.out / f"transactions-selection-{mode.value}.png")
        transactions.table.clearSelection()
        transactions.table.hovered_row = -1
        # The notifications panel, with a new version announced and the last notice
        # already opened, gray and without its dot.
        window.show_page(PageId.DASHBOARD)
        news = Release("9.9.0", "")
        window._show_release(news)
        notices = window.notices()
        services.notifications.mark_seen(notices[-1])
        window.open_notifications()
        app.processEvents()
        save(window.notification_panel, args.out / f"notifications-{mode.value}.png")
        window.notification_panel.hide()
        services.settings.set_seen_notices(set())
        window._show_release(None)
        # Updating from Nodus, halfway through the download (never started: no network).
        size = 24_578_342
        release = Release("9.9.0", "", installer=Installer("", size, ""))
        update = UpdateDialog(services.updates, release, parent=window)
        update.progressed.emit(size // 2)
        update.show()
        app.processEvents()
        save(update, args.out / f"update-dialog-{mode.value}.png")
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
        app.processEvents()
        save(error, args.out / f"user-error-{mode.value}.png")
        error.close()
    window.close()


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
    skip = next(action for action in page.rows[0].actions() if action.text == "Omitir")
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
    seen = next(action for action in row.actions() if action.text == "Ya lo vi")
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
    app: QApplication, services, event_bus: EventBus, window: MainWindow, out: Path, mode
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
    for _ in range(SETTLE_PASSES):
        QApplication.processEvents()
    widget.grab().save(str(path))
    print(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("screenshots"))
    parser.add_argument("--demo", action="store_true", help="load sample accounts and movements")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # Charts are captured in their final state, not halfway through their transitions.
    set_reduced_motion(True)
    app = QApplication(sys.argv)
    with tempfile.TemporaryDirectory() as data_dir:
        database = Database.open(Path(data_dir) / "nodus.db")
        try:
            render_pages(app, Services.create(database), args)
        finally:
            database.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
