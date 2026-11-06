from datetime import date
from decimal import Decimal

from factories import ars, category_id, expense_draft, income_draft
from PySide6.QtWidgets import QLabel

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.ui.navigation import PageId
from nodus.ui.pages.dashboard_cards import LatestTransactionRow, percent
from nodus.ui.widgets.elided_label import ElidedLabel


def dashboard(window):
    return window.page(PageId.DASHBOARD)


def visible_texts(page) -> list[str]:
    return [label.text() for label in page.findChildren(QLabel) if label.isVisibleTo(page)]


def test_welcome_leads_to_accounts_when_there_are_none(qtbot, window):
    page = dashboard(window)
    assert "Te damos la bienvenida a Nodus" in visible_texts(page)

    page.create_account_button.click()

    assert window.current_page is window.page(PageId.ACCOUNTS)


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
    assert "$ 250,00" in texts  # the donut legend line of the only category
    rows = [r for r in page.findChildren(LatestTransactionRow) if r.isVisibleTo(page)]
    descriptions = [label.text() for row in rows for label in row.findChildren(ElidedLabel)]
    assert "Verdulería" in descriptions and "Sueldo" in descriptions


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


def test_clicking_a_category_opens_its_transactions_in_the_period(qtbot, window, services, pesos):
    record_this_month(services, pesos)
    record_this_month(services, pesos, "100", "Transporte")
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)
    period = Period.of_months(Month.of(date.today()))

    page.expenses_card.rows[1].clicked.emit()  # Transporte, the second largest

    transactions = window.page(PageId.TRANSACTIONS)
    assert window.current_page is transactions
    assert transactions.period_selector.period() == period
    assert transactions.category_filter.current_id() == category_id(
        services, "Transporte", TransactionType.EXPENSE
    )
    assert transactions.model.rowCount() == 1


def test_clicking_a_donut_slice_and_a_comparison_row(qtbot, window, services, pesos):
    record_this_month(services, pesos)
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)
    supermarket = category_id(services, "Supermercado y comida", TransactionType.EXPENSE)

    with qtbot.waitSignal(page.transactions_requested) as from_donut:
        page.expenses_card.donut.segment_clicked.emit(0)
    window.show_page(PageId.DASHBOARD)
    with qtbot.waitSignal(page.transactions_requested) as from_comparison:
        page.comparison_card.rows[0].clicked.emit()

    assert from_donut.args[1] == supermarket
    assert from_comparison.args[1] == supermarket


def test_new_transaction_updates_the_same_cards(qtbot, window, services, event_bus, pesos):
    page = dashboard(window)
    window.show_page(PageId.DASHBOARD)
    cards = (page.net_worth_card, page.flow_card, page.expenses_card, page.comparison_card)
    chart = page.net_worth_card.chart

    record_this_month(services, pesos, "30000")
    event_bus.transactions_changed.emit()

    assert (page.net_worth_card, page.flow_card, page.expenses_card, page.comparison_card) == cards
    assert page.net_worth_card.chart is chart
    assert chart.points()[-1].value == ars("70000").cents
    assert page.flow_card.expenses_label.money() == ars("-30000")
    assert page.expenses_card.donut.segments()[0].value == ars("30000").cents


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
