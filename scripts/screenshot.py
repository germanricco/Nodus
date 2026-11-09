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

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from nodus.database.database import Database  # noqa: E402
from nodus.models.money import Money  # noqa: E402
from nodus.models.period import Month  # noqa: E402
from nodus.models.transaction import TransactionType  # noqa: E402
from nodus.models.transaction_filter import TransactionFilter  # noqa: E402
from nodus.services.container import Services  # noqa: E402
from nodus.services.update_service import Installer, Release  # noqa: E402
from nodus.ui.dialogs.account_dialog import AccountDialog  # noqa: E402
from nodus.ui.dialogs.budget_dialog import BudgetDialog  # noqa: E402
from nodus.ui.dialogs.category_dialog import CategoryDialog  # noqa: E402
from nodus.ui.dialogs.refund_picker import RefundPickerDialog  # noqa: E402
from nodus.ui.dialogs.transaction_dialog import TRANSFER_MODE, TransactionDialog  # noqa: E402
from nodus.ui.dialogs.update_dialog import UpdateDialog  # noqa: E402
from nodus.ui.dialogs.value_adjustment_dialog import ValueAdjustmentDialog  # noqa: E402
from nodus.ui.event_bus import EventBus  # noqa: E402
from nodus.ui.main_window import MainWindow  # noqa: E402
from nodus.ui.navigation import PageId  # noqa: E402
from nodus.ui.pages.accounts_page import AccountRow  # noqa: E402
from nodus.ui.theme.theme import ThemeMode  # noqa: E402
from nodus.ui.theme.theme_manager import ThemeManager  # noqa: E402
from nodus.ui.widgets import chart_base  # noqa: E402

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
    "transfer-dialog": lambda services, event_bus, window: transfer_dialog(
        services, event_bus, window
    ),
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
}


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


# File names of the analysis tabs, in their order.
ANALYSIS_TABS = ("trends", "cash-flow", "net-worth")


def render_pages(app: QApplication, services: Services, args: argparse.Namespace) -> None:
    if args.demo:
        load_demo_data(services, args.today)
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
        for name, build_dialog in DIALOGS.items():
            dialog = build_dialog(services, event_bus, window)
            dialog.show()
            app.processEvents()
            save(dialog, args.out / f"{name}-{mode.value}.png")
            dialog.close()
        # The color wheel, opened from the category dialog's «+» swatch.
        dialog = CategoryDialog(services, event_bus, parent=window)
        dialog.show()
        dialog.color_input.open_wheel()
        dialog.color_input.wheel_popup.set_color("#2a9d8f")
        app.processEvents()
        save(dialog.color_input.wheel_popup, args.out / f"color-wheel-{mode.value}.png")
        dialog.close()
        # The whole dashboard, below the fold too.
        window.resize(window.width(), FULL_DASHBOARD_HEIGHT)
        window.show_page(PageId.DASHBOARD)
        app.processEvents()
        save(window, args.out / f"dashboard-full-{mode.value}.png")
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
        row = next(r for r in accounts.findChildren(AccountRow) if r.can_update_value)
        row.more_button.open_menu()
        app.processEvents()
        save(row.more_button.menu, args.out / f"row-menu-{mode.value}.png")
        row.more_button.menu.close()
        # The notifications panel, with a new version announced.
        window.show_page(PageId.DASHBOARD)
        window._show_release(Release("9.9.0", ""))
        window.open_notifications()
        app.processEvents()
        save(window.notification_panel, args.out / f"notifications-{mode.value}.png")
        window.notification_panel.hide()
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
    window.close()


def save(widget: QWidget, path: Path) -> None:
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
    chart_base.DURATION_MS = 0
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
