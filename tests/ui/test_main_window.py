import time
from datetime import date
from decimal import Decimal

from demo_data import load_demo_data
from factories import ars, expense_draft, services_for
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from qt_cleanup import flush_deleted

from nodus.config.paths import AppPaths
from nodus.database.database import Database
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.container import Services
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import PageId
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.shell.sidebar import Sidebar, SidebarAccountRow


def sidebar_texts(window) -> list[str]:
    return [label.text() for label in window.sidebar.findChildren(QLabel) if label.isVisible()]


def test_a_closed_window_frees_its_widgets(qapp, services, event_bus, theme_manager):
    """Nothing may keep a closed window alive: each one left behind slows every later test."""
    flush_deleted()
    before = len(QApplication.allWidgets())
    main_window = MainWindow(services, event_bus, theme_manager)
    main_window.show()
    assert len(QApplication.allWidgets()) > before + 100

    main_window.close()
    main_window.deleteLater()
    del main_window
    flush_deleted()

    assert len(QApplication.allWidgets()) <= before + 5


def test_opens_on_dashboard(window):
    assert window.isVisible()
    assert window.windowTitle() == "Nodus"
    assert window.current_page is window.page(PageId.DASHBOARD)


def test_sidebar_buttons_navigate(window, qtbot):
    for page_id in PageId:
        button = window.sidebar.nav_button(page_id)
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

        assert window.current_page is window.page(page_id)
        assert button.isChecked()


def test_edit_in_a_transactions_filter_opens_its_page(window):
    window.show_page(PageId.TRANSACTIONS)
    combo = window.page(PageId.TRANSACTIONS).category_filter

    combo.view().pressed.emit(combo.model().index(combo.count() - 1, 0))

    assert window.current_page is window.page(PageId.CATEGORIES)
    assert window.sidebar.nav_button(PageId.CATEGORIES).isChecked()


def test_sidebar_shows_empty_state_without_accounts(window):
    assert "Todavía no hay cuentas" in sidebar_texts(window)


def test_sidebar_lists_accounts_with_balances(window, qtbot, pesos, dollars):
    window.sidebar.refresh_accounts()

    # Qt shows widgets added to a visible parent on the next event loop pass.
    qtbot.waitUntil(lambda: "Banco" in sidebar_texts(window))
    texts = sidebar_texts(window)
    assert "$ 100.000,00" in texts
    assert "US$ 500,00" in texts
    assert "Todavía no hay cuentas" not in texts


def test_sidebar_refreshes_when_data_changes(window, services, event_bus, qtbot, pesos):
    window.sidebar.refresh_accounts()
    services.transactions.create(expense_draft(services, pesos.id, ars("2500")))
    services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))

    event_bus.transactions_changed.emit()

    qtbot.waitUntil(lambda: "$ 97.500,00" in sidebar_texts(window))
    assert "Efectivo" in sidebar_texts(window)


def test_sidebar_collapses_to_icons_and_remembers_it(
    window, qtbot, services, event_bus, theme_manager, pesos
):
    window.sidebar.refresh_accounts()
    button = window.sidebar.nav_button(PageId.BUDGETS)

    window.sidebar.collapse_button.click()

    assert window.sidebar.width() == Sidebar.COLLAPSED_WIDTH
    assert button.text() == ""
    assert button.toolTip() == "Presupuestos (Ctrl+5)"
    assert "Banco" not in sidebar_texts(window)
    reopened = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(reopened)
    assert reopened.sidebar.is_collapsed

    window.sidebar.collapse_button.click()

    assert button.text() == PageId.BUDGETS.label
    assert not services.settings.sidebar_collapsed()


def test_collapsed_the_accounts_button_tells_the_balances(window, services, pesos):
    window.sidebar.refresh_accounts()
    window.sidebar.collapse_button.click()
    button = window.sidebar.nav_button(PageId.ACCOUNTS)

    assert button.toolTip() == "Cuentas (Ctrl+2)\n\nTotal: $ 100.000,00\nBanco: $ 100.000,00"

    window.toggle_amounts_hidden()

    assert "100.000" not in button.toolTip()
    assert "Banco: $ ••••" in button.toolTip()


def test_eye_hides_balances_and_net_worth_and_remembers_it(
    window, qtbot, services, event_bus, theme_manager, pesos
):
    window.sidebar.refresh_accounts()
    window.show_page(PageId.ACCOUNTS)
    accounts = window.page(PageId.ACCOUNTS)

    window.top_bar.hide_amounts_button.click()

    qtbot.waitUntil(lambda: "$ ••••" in sidebar_texts(window))
    assert "$ 100.000,00" not in sidebar_texts(window)
    balances = [label.text() for label in accounts.findChildren(QLabel) if label.isVisible()]
    assert "$ 100.000,00" not in balances
    assert accounts.net_worth_card.total_label.text() == "$ ••••"
    window.show_page(PageId.DASHBOARD)
    assert window.page(PageId.DASHBOARD).net_worth_card.total_label.text() == "$ ••••"
    assert window.top_bar.hide_amounts_button.toolTip() == "Mostrar montos (Ctrl+H)"
    reopened = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(reopened)
    assert reopened.top_bar.hide_amounts_button.toolTip() == "Mostrar montos (Ctrl+H)"

    window.top_bar.hide_amounts_button.click()

    qtbot.waitUntil(lambda: "$ 100.000,00" in sidebar_texts(window))
    assert not services.settings.amounts_hidden()


def test_accounts_fold_under_their_title(window, qtbot, services, pesos):
    window.sidebar.refresh_accounts()
    qtbot.waitUntil(lambda: "Banco" in sidebar_texts(window))

    window.sidebar.toggle_accounts_folded()

    assert "Banco" not in sidebar_texts(window)
    assert services.settings.accounts_folded()
    window.sidebar.toggle_accounts_folded()
    assert "Banco" in sidebar_texts(window)


class _StrayWindowSpy(QObject):
    """Records every widget that shows as a window of its own while installed."""

    def __init__(self) -> None:
        super().__init__()
        self.shown: list[str] = []

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
            and watched.windowType() == Qt.WindowType.Window
            and not isinstance(watched, MainWindow)
        ):
            self.shown.append(f"{type(watched).__name__} {watched.objectName()!r}")
        return False


def test_refreshing_never_flashes_a_stray_window(qtbot, qapp, window, services, event_bus):
    """A widget made visible before it has a parent shows for an instant as a window."""
    load_demo_data(services, date.today())
    spy = _StrayWindowSpy()
    qapp.installEventFilter(spy)
    try:
        for page_id in PageId:
            window.show_page(page_id)
            window.toggle_amounts_hidden()
            window.toggle_amounts_hidden()
        for signal in (
            event_bus.accounts_changed,
            event_bus.transactions_changed,
            event_bus.recurring_changed,
            event_bus.budgets_changed,
            event_bus.exchange_rates_changed,
        ):
            signal.emit()
        qtbot.wait(50)
    finally:
        qapp.removeEventFilter(spy)

    assert spy.shown == []


def test_settings_sits_at_the_foot_of_the_sidebar(window):
    layout = window.sidebar.layout()
    settings = layout.indexOf(window.sidebar.nav_button(PageId.SETTINGS))

    # Below the other pages and the accounts, and no longer in the top bar.
    assert settings > layout.indexOf(window.sidebar.nav_button(PageId.TAGS)) + 1
    assert not hasattr(window.top_bar, "settings_button")


class TestSidebarGroups:
    """Accounts by group in the sidebar; Qt shows rebuilt rows on the next loop pass."""

    def test_accounts_show_under_their_group_and_loose_ones_last(
        self, window, qtbot, services, event_bus, pesos, dollars
    ):
        bancos = services.account_groups.create("Bancos")
        services.account_groups.create("Vacío")
        services.account_groups.move_account(pesos.id, bancos.id)
        event_bus.accounts_changed.emit()

        qtbot.waitUntil(lambda: "▾  Bancos" in sidebar_texts(window))
        texts = sidebar_texts(window)
        assert texts.index("▾  Bancos") < texts.index("Banco") < texts.index("Ahorro")
        assert "▾  Vacío" not in texts  # a group with no accounts is left out

    def test_a_folded_group_shows_its_subtotal_and_is_remembered(
        self, window, qtbot, services, event_bus, pesos
    ):
        bancos = services.account_groups.create("Bancos")
        services.account_groups.move_account(pesos.id, bancos.id)
        event_bus.accounts_changed.emit()

        qtbot.mouseClick(window.sidebar.group_rows[bancos.id], Qt.MouseButton.LeftButton)

        qtbot.waitUntil(lambda: "▸  Bancos" in sidebar_texts(window))
        texts = sidebar_texts(window)
        assert "$ 100.000,00" in texts
        assert "Banco" not in texts
        assert services.settings.folded_groups() == {bancos.id}

    def test_a_long_name_gives_way_so_the_cents_show(self, window, qtbot, services, event_bus):
        account = services.accounts.create(
            "Caja de ahorro del banco de siempre", AccountType.BANK, Currency.ARS,
            ars("12345678.90"),
        )  # fmt: skip
        bancos = services.account_groups.create("Bancos")
        services.account_groups.move_account(account.id, bancos.id)
        event_bus.accounts_changed.emit()
        qtbot.waitUntil(lambda: "$ 12.345.678,90" in sidebar_texts(window))

        row = window.sidebar.findChild(SidebarAccountRow)
        assert row.amount_label.width() >= row.amount_label.sizeHint().width()
        assert row.name_label.width() < row.name_label.sizeHint().width()

    def test_a_mixed_group_follows_the_net_worth_currency(
        self, window, qtbot, services, event_bus, pesos, dollars
    ):
        services.exchange_rates.set_rate(date.today(), Decimal("1000"))
        todo = services.account_groups.create("Todo")
        for account in (pesos, dollars):
            services.account_groups.move_account(account.id, todo.id)
        services.settings.set_folded_groups({todo.id})
        event_bus.accounts_changed.emit()
        qtbot.waitUntil(lambda: "≈ $ 600.000,00" in sidebar_texts(window))

        window.page(PageId.DASHBOARD).net_worth_card.currency_input.buttons[1].click()

        qtbot.waitUntil(lambda: "≈ US$ 600,00" in sidebar_texts(window))


class TestPagesOnDemand:
    """Opening the window pays for Inicio only; other pages wait until they are shown."""

    def test_only_inicio_is_built_on_opening(self, window):
        assert list(window._pages) == [PageId.DASHBOARD]
        assert window._details == {}

    def test_a_page_is_built_and_filled_when_first_asked_for(self, window, pesos):
        accounts = window.page(PageId.ACCOUNTS)

        assert window.page(PageId.ACCOUNTS) is accounts
        assert "Banco" in [label.text() for label in accounts.findChildren(QLabel)]

    def test_a_page_put_aside_waits_until_shown(self, monkeypatch, window, event_bus, pesos):
        window.show_page(PageId.ACCOUNTS)
        window.show_page(PageId.DASHBOARD)
        accounts = window.page(PageId.ACCOUNTS)
        refreshed = []
        monkeypatch.setattr(accounts, "refresh", lambda: refreshed.append(True))

        event_bus.accounts_changed.emit()
        assert refreshed == []

        window.show_page(PageId.ACCOUNTS)
        assert refreshed == [True]

    def test_the_page_in_view_follows_the_data(self, monkeypatch, window, event_bus, pesos):
        window.show_page(PageId.ACCOUNTS)
        accounts = window.page(PageId.ACCOUNTS)
        refreshed = []
        monkeypatch.setattr(accounts, "refresh", lambda: refreshed.append(True))

        event_bus.accounts_changed.emit()

        assert refreshed == [True]


START_LIMIT_SECONDS = 2.0  # opens in 0.1 to 0.4 s; the margin is for the CI and -n auto


def test_opens_quickly_over_a_year_of_data(qtbot, tmp_path, theme_manager):
    """From the file to the painted window, as at every start, over the demo data (a year
    of movements, budgets, charges and goals): what makes it slow shows here first."""
    path = AppPaths(tmp_path).database_path
    database = Database.open(path)
    load_demo_data(services_for(database), date.today())
    services_for(database).settings.set_tour_offered(True)
    database.close()

    started = time.perf_counter()
    database = Database.open(path)
    services = Services.create(database, AppPaths(tmp_path).backups_dir)
    services.backups.create_if_due(date.today())
    window = MainWindow(services, EventBus(), theme_manager)
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    elapsed = time.perf_counter() - started

    database.close()
    assert elapsed < START_LIMIT_SECONDS, f"Nodus took {elapsed:.2f} s to open"
