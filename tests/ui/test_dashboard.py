from datetime import date, timedelta
from decimal import Decimal

import pytest
from factories import (
    ars,
    category_id,
    charge_draft,
    clp,
    eur,
    expense_draft,
    income_draft,
    services_for,
    usd,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from nodus.database.database import Database
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.services.transactions.transfer_service import TransferDraft
from nodus.ui.actions import recurring as recurring_actions
from nodus.ui.dialogs import restore_copy
from nodus.ui.navigation import DetailId, PageId, RecordLink
from nodus.ui.pages.dashboard.dashboard_page import Shape
from nodus.ui.shell import main_window
from nodus.ui.shell.main_window import MainWindow
from nodus.ui.text.formatting import percent
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.tables.transaction_table import AMOUNT, MOVEMENT, CompactMovementRow


def dashboard(window):
    return window.page(PageId.DASHBOARD)


def visible_texts(page) -> list[str]:
    return [label.text() for label in page.findChildren(QLabel) if label.isVisibleTo(page)]


def test_welcome_leads_to_accounts(qtbot, window, services):
    page = dashboard(window)
    page.refresh()
    assert "Te damos la bienvenida a Nodus" in visible_texts(page)

    page.create_account_button.click()

    assert window.current_page is window.page(PageId.ACCOUNTS)


def test_a_new_computer_brings_the_data_from_the_old_one(
    qtbot, window, services, monkeypatch, tmp_path
):
    """Nodus on a new computer: the copy saved on the old one, on a pen drive, opens from
    the Inicio as it was there, settings included."""
    (tmp_path / "vieja").mkdir()
    old_computer = Database.open(tmp_path / "vieja" / "nodus.db")
    old = services_for(old_computer)
    old.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("1000"))
    old.settings.set_amounts_hidden(True)
    pen_drive = tmp_path / "pendrive"
    pen_drive.mkdir()
    copy = old.backups.export_to(pen_drive, date.today())
    old_computer.close()
    monkeypatch.setattr(restore_copy.QFileDialog, "getOpenFileName", lambda *_a: (str(copy), ""))
    monkeypatch.setattr(restore_copy, "confirm", lambda *_a, **_k: True)
    asked = []
    monkeypatch.setattr(main_window, "ask", lambda _p, _t, text, *_: asked.append(text))
    page = dashboard(window)
    page.refresh()

    page.bring_data_button.click()

    assert [a.name for a in services.accounts.list_accounts()] == ["Banco"]
    assert services.settings.amounts_hidden()
    assert "Te damos la bienvenida a Nodus" not in visible_texts(page)
    # The copy predates the tour, but whoever brings their data has used Nodus.
    qtbot.wait(10)
    assert asked == []
    assert services.settings.tour_offered()


def test_a_transfer_between_currencies_shows_what_left(
    qtbot, window, services, event_bus, pesos, dollars
):
    """One amount leaves the name its room; what arrived shows under the mouse."""
    services.transfers.create(
        TransferDraft(pesos.id, dollars.id, ars("243100"), date.today(), amount_in=usd("200"))
    )
    event_bus.transactions_changed.emit()
    page = dashboard(window)
    page.refresh()

    qtbot.waitUntil(lambda: bool(latest_rows(page)))  # rows come next pass
    (row,) = latest_rows(page)
    amount = row.cells()[AMOUNT]
    assert row.model.index(row.row, AMOUNT).data() == "$ 243.100,00"
    assert row.tooltip_at(amount.center()) == "$ 243.100,00 → US$ 200,00"


def latest_rows(page) -> list[CompactMovementRow]:
    return [r for r in page.latest_card.rows() if r.isVisibleTo(page)]


def test_shows_month_flow_and_latest_movements(qtbot, window, services, event_bus, pesos):
    month = Month.of(date.today())
    services.transactions.create(
        income_draft(services, pesos.id, ars("1000"), on=month.start, note="Sueldo")
    )
    services.transactions.create(
        expense_draft(services, pesos.id, ars("250"), on=month.start, note="Verdulería")
    )

    event_bus.transactions_changed.emit()

    page = dashboard(window)
    # New rows are shown on the next pass of the event loop.
    qtbot.waitUntil(lambda: {"$ 750,00", "$ 250,00"} <= set(visible_texts(page)))
    texts = visible_texts(page)
    assert "75 %" in texts
    assert "$ 250,00" in texts  # the line of the only category

    def descriptions() -> list[str]:
        return [row.model.index(row.row, MOVEMENT).data() for row in latest_rows(page)]

    qtbot.waitUntil(lambda: {"Verdulería", "Sueldo"} <= set(descriptions()))


def test_see_all_opens_transactions_on_the_same_period(qtbot, window, pesos):
    page = dashboard(window)
    page.refresh()
    previous = Period.of_months(Month.of(date.today()).previous())
    page.period_selector.set_period(previous)

    page.see_all_button.click()

    assert window.current_page is window.page(PageId.TRANSACTIONS)
    assert window.page(PageId.TRANSACTIONS).period_selector.period() == previous


def test_percent_needs_positive_whole():
    assert percent(ars("1"), ars("3")) == "33 %"
    assert percent(ars("1"), ars("0")) == "—"


def record_this_month(services, pesos, amount="250", category="Supermercado y comida"):
    services.transactions.create(
        expense_draft(
            services,
            pesos.id,
            ars(amount),
            on=date.today(),
            category_id=category_id(services, category, TransactionType.EXPENSE),
        )
    )


def test_clicking_a_category_opens_its_page(qtbot, window, services, pesos):
    record_this_month(services, pesos)
    record_this_month(services, pesos, "100", "Transporte")
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)

    # Transporte, the second largest.
    qtbot.mouseClick(page.categories_card.rows[1], Qt.MouseButton.LeftButton)

    detail = window.detail(DetailId.CATEGORY)
    assert window.current_page is detail
    assert detail.item_id == category_id(services, "Transporte", TransactionType.EXPENSE)


def test_categories_go_from_the_total_to_each_against_the_period_before(
    qtbot, window, services, pesos
):
    """The total spent under the title, then the six that took the most, each with its
    share, amount and change; the rest add up in one line that opens nothing."""
    month_ago = date.today() - timedelta(days=31)
    names = (
        "Supermercado y comida",
        "Vivienda",
        "Servicios",
        "Transporte",
        "Salud",
        "Educación",
        "Ocio",
        "Ropa",
    )
    for amount, name in zip(range(800, 0, -100), names, strict=True):
        record_this_month(services, pesos, str(amount), name)
    services.transactions.create(
        expense_draft(
            services,
            pesos.id,
            ars("400"),
            on=month_ago,
            category_id=category_id(services, "Supermercado y comida", TransactionType.EXPENSE),
        )
    )
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)
    card = page.categories_card

    assert card.total_label.text() == "$ 3.600,00"
    assert [row.name for row in card.rows] == [*names[:6], "Resto"]
    first, rest = card.rows[0], card.rows[-1]
    assert first.findChild(ChangeBadge).text() == "↗ 100 %"
    assert card.bars[first.link.item_id].fraction == pytest.approx(800 / 3600)
    assert rest.link is None
    assert "$ 300,00" in [label.text() for label in rest.findChildren(QLabel)]  # 200 + 100


def test_new_transaction_updates_the_same_cards(qtbot, window, services, event_bus, pesos):
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)
    cards = (page.net_worth_card, page.flow_card, page.categories_card)
    chart = page.net_worth_card.chart

    record_this_month(services, pesos, "30000")
    event_bus.transactions_changed.emit()

    assert (page.net_worth_card, page.flow_card, page.categories_card) == cards
    assert page.net_worth_card.chart is chart
    assert chart.points()[-1].value == ars("70000").cents
    assert page.flow_card.expenses_label.money() == ars("-30000")
    assert page.categories_card.total_label.text() == "$ 30.000,00"


def test_hidden_dashboard_waits_until_shown(qtbot, window, services, event_bus, pesos, monkeypatch):
    window.show_page(PageId.ACCOUNTS)
    page = dashboard(window)
    refreshes = []
    monkeypatch.setattr(page, "refresh", lambda: refreshes.append(1))

    event_bus.transactions_changed.emit()
    assert refreshes == []

    window.show_page(PageId.DASHBOARD)
    assert refreshes == [1]


def test_net_worth_currency_switch_redraws_the_trend(qtbot, window, services, pesos, dollars):
    services.exchange_rates.set_rate(date.today().replace(day=1), Decimal("1000"))
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)
    card = page.net_worth_card

    card.currency_input.set_index(1)

    assert card.total_label.text() == "US$ 600,00"
    assert card.chart.points()[-1].value == ars("600").cents  # cents of US$ 600


def test_net_worth_names_the_day_only_when_it_is_not_today(qtbot, window, services, pesos):
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)
    card = page.net_worth_card
    assert not card.day_label.isVisibleTo(card)

    card.show_day(date(2026, 9, 30))

    assert card.day_label.isVisibleTo(card)
    assert card.day_label.text() == "al 30/09/2026"


def test_upcoming_payments_appear_with_active_charges(
    qtbot, window, services, event_bus, pesos, monkeypatch
):
    page = dashboard(window)
    page.refresh()
    assert not page.upcoming_card.isVisibleTo(page)

    charge = services.recurring.create(
        charge_draft(services, pesos.id, ars("8500"), date.today(), name="Netflix")
    )
    event_bus.recurring_changed.emit()

    assert page.upcoming_card.isVisibleTo(page)
    (row,) = page.upcoming_card.rows
    assert row.charge.name == "Netflix"
    assert page.upcoming_card.monthly_label.text() == "~$ 8.500,00/mes"

    opened = []
    monkeypatch.setattr(
        recurring_actions,
        "PayChargeDialog",
        lambda _s, _e, c, parent=None: opened.append(c) or NoDialog(),
    )
    row.pay_button.click()
    assert opened == [services.recurring.get(charge.id)]

    page.upcoming_card.see_all_button.click()
    assert window.current_page is window.page(PageId.RECURRING)


def test_upcoming_card_says_when_nothing_is_due_soon(qtbot, window, services, pesos):
    services.recurring.create(
        charge_draft(services, pesos.id, ars("1"), date.today() + timedelta(days=30))
    )
    page = dashboard(window)
    page.refresh()

    assert page.upcoming_card.rows == []
    qtbot.waitUntil(
        lambda: "Nada que pagar en los próximos 14 días" in visible_texts(page.upcoming_card)
    )


class NoDialog:
    def exec(self) -> int:
        return 0


def grid_cell(page, card) -> tuple[int, int, int, int]:
    return page._grid.getItemPosition(page._grid.indexOf(card))


def test_cards_rearrange_for_narrow_windows(qtbot, window, services, pesos):
    services.recurring.create(charge_draft(services, pesos.id, ars("1"), date.today()))
    page = dashboard(window)
    window.resize(1400, 900)
    page.refresh()
    qtbot.waitUntil(lambda: grid_cell(page, page.upcoming_card) == (0, 4, 1, 2))
    # «How much is left?» comes before where the money went.
    assert grid_cell(page, page.flow_card)[0] < grid_cell(page, page.categories_card)[0]

    window.resize(1100, 900)
    window.toggle_help()  # Ayuda beside it leaves the page too narrow for two columns

    qtbot.waitUntil(lambda: grid_cell(page, page.upcoming_card)[:2] == (1, 0))
    assert grid_cell(page, page.categories_card)[0] > grid_cell(page, page.flow_card)[0]


def test_opens_with_the_shape_of_its_window(qtbot, services, event_bus, theme_manager, pesos):
    """The shape is chosen once the page has its real width, with no resize to fix it:
    a page built before the window is shown must not keep its first, narrow guess."""
    window = MainWindow(services, event_bus, theme_manager)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    page = dashboard(window)

    qtbot.waitUntil(lambda: page._layout is not None and page._layout[0] is Shape.WIDE)


@pytest.mark.parametrize("width", range(1500, 1080, -40))
def test_no_card_is_cut_at_any_width(qtbot, window, services, event_bus, pesos, width):
    """The cards change shape before any of them gets less than its minimum width: the
    grid never asks for more than the page shows. Long names and amounts make a side
    card this wide, which the six columns of a 1280-wide window cannot hold."""
    services.recurring.create(charge_draft(services, pesos.id, ars("24900"), date.today()))
    food = category_id(services, "Supermercado y comida", TransactionType.EXPENSE)
    services.budgets.set_limit(food, Month.of(date.today()), ars("1000"))
    event_bus.budgets_changed.emit()
    page = dashboard(window)
    page.upcoming_card.setMinimumWidth(420)
    page.refresh()

    window.resize(width, 900)

    def fits() -> bool:
        needed = page._scroll.widget().minimumSizeHint().width()
        return needed <= page._scroll.viewport().width()

    qtbot.waitUntil(fits)


def test_ayuda_folds_the_sidebar_when_the_page_would_be_cut(qtbot, window, pesos):
    """With the window at its narrowest, Ayuda beside it leaves the Inicio less than its
    narrowest shape needs: the sidebar folds while Ayuda is open, and comes back."""
    page = dashboard(window)
    page.net_worth_card.setMinimumWidth(560)  # as wide as it gets with long figures
    window.resize(1100, 900)
    page.refresh()
    assert not window.sidebar.is_collapsed

    window.toggle_help()

    qtbot.waitUntil(lambda: window.sidebar.is_collapsed)
    needed = page._scroll.widget().minimumSizeHint().width()
    qtbot.waitUntil(lambda: needed <= page._scroll.viewport().width())
    window.toggle_help()
    assert not window.sidebar.is_collapsed


def test_a_sidebar_folded_by_hand_stays_folded_after_ayuda(qtbot, window, pesos):
    page = dashboard(window)
    page.net_worth_card.setMinimumWidth(560)
    window.resize(1100, 900)
    page.refresh()
    window.toggle_help()
    qtbot.waitUntil(lambda: window.sidebar.is_collapsed)

    window.sidebar.collapse_button.click()  # unfolded by hand: the user's choice now
    window.sidebar.collapse_button.click()  # and folded again
    window.toggle_help()

    assert window.sidebar.is_collapsed


def test_budgets_card_sits_beside_the_cash_flow_when_there_are_budgets(
    qtbot, window, services, event_bus, pesos
):
    page = dashboard(window)
    window.resize(1400, 900)
    page.refresh()
    assert not page.budgets_card.isVisibleTo(page)
    qtbot.waitUntil(lambda: grid_cell(page, page.flow_card)[3] == 6)

    food = category_id(services, "Supermercado y comida", TransactionType.EXPENSE)
    services.budgets.set_limit(food, Month.of(date.today()), ars("1000"))
    event_bus.budgets_changed.emit()

    assert page.budgets_card.isVisibleTo(page)
    qtbot.waitUntil(lambda: grid_cell(page, page.flow_card)[3] == 4)
    flow_row = grid_cell(page, page.flow_card)[0]
    assert grid_cell(page, page.budgets_card) == (flow_row, 4, 1, 2)


def test_budgets_card_lists_the_closest_to_their_limit(qtbot, window, services, pesos):
    month = Month.of(date.today())
    for name, limit in (("Supermercado y comida", "1000"), ("Ocio", "100"), ("Salud", "500"),
                        ("Ropa", "500"), ("Transporte", "500")):  # fmt: skip
        services.budgets.set_limit(
            category_id(services, name, TransactionType.EXPENSE), month, ars(limit)
        )
    leisure = category_id(services, "Ocio", TransactionType.EXPENSE)
    services.transactions.create(
        expense_draft(services, pesos.id, ars("90"), on=date.today(), category_id=leisure)
    )
    page = dashboard(window)
    page.refresh()
    card = page.budgets_card

    assert len(card.rows) == 4
    assert card.rows[0].budget.category.name == "Ocio"

    with qtbot.waitSignal(page.record_requested) as signal:
        qtbot.mouseClick(card.rows[0].line, Qt.MouseButton.LeftButton)
    assert signal.args == [RecordLink.category(leisure)]

    card.see_all_button.click()
    assert window.current_page is window.page(PageId.BUDGETS)


def test_cards_are_never_squeezed_when_the_theme_changes(qtbot, window, theme_manager, pesos):
    from nodus.ui.theme.theme_manager import ThemeMode

    page = dashboard(window)
    window.resize(1280, 700)
    window.show_page(PageId.DASHBOARD)
    theme_manager.set_mode(ThemeMode.DARK)

    def fits() -> bool:
        grid_page = page._grid.parentWidget()
        return grid_page.height() >= page._grid.minimumSize().height()

    qtbot.waitUntil(fits)


def test_many_currencies_never_push_the_cards_off_the_window(
    qtbot, window, services, pesos, dollars
):
    services.accounts.create("Viaje", AccountType.CASH, Currency.EUR, eur("150"))
    services.accounts.create("Chile", AccountType.CASH, Currency.CLP, clp("90000"))
    window.resize(1280, 800)
    window.show_page(PageId.DASHBOARD)
    qtbot.wait(50)

    page = window.page(PageId.DASHBOARD)
    scroll = page.findChild(QScrollArea)
    assert scroll.widget().width() <= scroll.viewport().width()


def test_a_month_of_the_cash_flow_opens_its_movements(qtbot, window, services, pesos):
    """As in Análisis, a month of «Flujo de caja» opens that month's movements."""
    month = Month.of(date.today())
    services.transactions.create(expense_draft(services, pesos.id, ars("250"), on=month.start))
    page = dashboard(window)
    page.refresh()
    groups = page.flow_card.chart.groups()
    index = next(i for i, group in enumerate(groups) if group.key == month)

    page.flow_card.chart.clicked.emit(index)

    assert window.current_page is window.page(PageId.TRANSACTIONS)
    assert window.page(PageId.TRANSACTIONS).period_selector.period() == Period.of_months(month)


def test_hiding_the_amounts_moves_nothing_on_the_net_worth(qtbot, window, services):
    """A masked amount keeps the width of the figure, so the legend under the chart does
    not fit in fewer lines and the chart does not grow (seen by the user)."""
    for name, currency, amount in (
        ("Banco", Currency.ARS, ars("1715086.85")),
        ("Ahorro", Currency.USD, usd("1350")),
        ("Viaje", Currency.EUR, eur("150")),
    ):
        services.accounts.create(name, AccountType.BANK, currency, amount)
    first = date.today().replace(day=1)
    services.exchange_rates.set_rate(first, Decimal("1215.50"))
    services.exchange_rates.set_rate(first, Decimal("1410"), Currency.EUR)
    window.resize(1100, 800)
    window.show_page(PageId.DASHBOARD)
    card = dashboard(window).net_worth_card
    QApplication.processEvents()
    shown = card.chart.height()
    legend = card.legends[Currency.ARS].amount

    window.toggle_amounts_hidden()
    QApplication.processEvents()

    assert legend.text().endswith("••••")
    assert legend.sizeHint().width() >= legend.fontMetrics().horizontalAdvance("$ 1.715.086,85")
    assert card.chart.height() == shown
