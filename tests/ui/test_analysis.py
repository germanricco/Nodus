"""The analysis page and its reports."""

from datetime import date

import pytest
from factories import ars, category_id, eur, expense_draft, income_draft
from PySide6.QtCore import Qt

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.period import Month, Period, format_month
from nodus.models.transaction import TransactionType
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages.analysis_page import AnalysisPage
from nodus.ui.pages.analysis_views import (
    NO_PAYEE_LABEL,
    NO_RATE_TEXT,
    CashFlowView,
    NetWorthView,
    TrendsView,
)

EXPENSE = TransactionType.EXPENSE
SEP_NOV = Period.of_months(Month(2026, 9), Month(2026, 11))
SAVINGS_TAB = 2
CASH_FLOW_TAB = 1
NET_WORTH_TAB = 2


@pytest.fixture
def movements(services, pesos):
    services.transactions.create(income_draft(services, pesos.id, ars("1000"), date(2026, 9, 1)))
    services.transactions.create(
        expense_draft(services, pesos.id, ars("300"), date(2026, 9, 5), payee_name="Coto")
    )
    services.transactions.create(
        expense_draft(
            services, pesos.id, ars("100"), date(2026, 10, 5),
            category_id=category_id(services, "Servicios", EXPENSE),
        )
    )  # fmt: skip


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> AnalysisPage:
    analysis = AnalysisPage(services, event_bus, theme_manager)
    qtbot.addWidget(analysis)
    analysis.resize(1100, 800)
    analysis.show()
    analysis.period_selector.set_period(SEP_NOV)
    return analysis


@pytest.fixture
def filled(page, movements) -> AnalysisPage:
    """The page after the movements are recorded, as the window would refresh it."""
    page.refresh()
    return page


def trends_view(page) -> TrendsView:
    return page.views[0]


def cash_flow_view(page) -> CashFlowView:
    page.tabs.set_index(CASH_FLOW_TAB)
    return page.views[CASH_FLOW_TAB]


def net_worth_view(page) -> NetWorthView:
    page.tabs.set_index(NET_WORTH_TAB)
    return page.views[NET_WORTH_TAB]


def table_row(view: CashFlowView | NetWorthView, row: int) -> list[str]:
    model = view.model
    return [model.index(row, column).data() for column in range(model.columnCount())]


def row_texts(layout) -> list[str]:
    return [layout.itemAt(i).widget().name for i in range(layout.count())]


def test_starts_on_the_last_twelve_months(qtbot, services, event_bus, theme_manager):
    analysis = AnalysisPage(services, event_bus, theme_manager)
    qtbot.addWidget(analysis)

    assert analysis.period_selector.period() == Period.last_months(12, date.today())


def test_expenses_trend_with_totals_and_breakdown(filled):
    view = trends_view(filled)

    assert view.total_label.money() == ars("400")
    assert view.average_label.text() == "$ 133,33"
    assert [bar.label for bar in view.chart.bars()] == ["Sep", "Oct", "Nov"]
    assert row_texts(view._category_rows) == ["Supermercado y comida", "Servicios"]
    assert row_texts(view._payee_rows) == ["Coto", NO_PAYEE_LABEL]


def test_savings_hides_the_breakdown(filled):
    view = trends_view(filled)

    view.metric_input.set_index(SAVINGS_TAB)

    assert view.total_label.money() == ars("600")
    assert [bar.segments[0].value for bar in view.chart.bars()] == [70000, -10000, 0]
    assert view.categories_card.isHidden()
    assert view.payees_card.isHidden()
    assert view.tags_card.isHidden()


def test_tags_card_shows_only_with_tagged_movements(qtbot, services, pesos, filled):
    view = trends_view(filled)
    assert view.tags_card.isHidden()

    services.transactions.create(
        expense_draft(services, pesos.id, ars("80"), date(2026, 10, 9), tag_names=("Viaje",))
    )
    filled.refresh()

    assert not view.tags_card.isHidden()
    assert row_texts(view._tag_rows) == ["Viaje"]
    with qtbot.waitSignal(filled.transactions_requested) as from_tag:
        view._tag_rows.itemAt(0).widget().clicked.emit()
    assert from_tag.args == [TransactionFocus(SEP_NOV, tag_id=services.tags.find("Viaje").id)]


def test_empty_period_says_so(page):
    view = trends_view(page)

    assert view.chart.isHidden()
    assert not view.empty_label.isHidden()


def test_bar_and_rows_lead_to_transactions(qtbot, filled, services):
    page = filled
    view = trends_view(page)
    servicios = category_id(services, "Servicios", EXPENSE)

    with qtbot.waitSignal(page.transactions_requested) as from_bar:
        view.chart.clicked.emit(1, servicios)
    assert from_bar.args == [TransactionFocus(Period.of_months(Month(2026, 10)), servicios)]

    with qtbot.waitSignal(page.transactions_requested) as from_payee:
        view._payee_rows.itemAt(0).widget().clicked.emit()
    assert from_payee.args == [TransactionFocus(SEP_NOV, payee_id=services.payees.find("Coto").id)]


def test_window_opens_transactions_filtered(window, services, movements):
    window.show_page(PageId.ANALYSIS)
    analysis = window.page(PageId.ANALYSIS)
    analysis.period_selector.set_period(SEP_NOV)
    servicios = category_id(services, "Servicios", EXPENSE)

    analysis.views[0].chart.clicked.emit(1, servicios)

    transactions = window.page(PageId.TRANSACTIONS)
    assert window.current_page is transactions
    assert transactions.period_selector.period() == Period.of_months(Month(2026, 10))
    assert transactions.category_filter.current_id() == servicios


# Cash flow


def test_cash_flow_totals_and_months(filled):
    view = cash_flow_view(filled)

    assert filled.current_view is view
    assert view.income_label.money() == ars("1000")
    assert view.expenses_label.money() == -ars("400")
    assert view.savings_label.money() == ars("600")
    assert view.rate_label.text() == "60 %"
    assert view.rate_badge.text() == "Sin datos del período anterior"
    assert [group.label for group in view.chart.groups()] == ["Sep", "Oct", "Nov"]
    assert view.model.rowCount() == 3
    assert table_row(view, 0) == [
        format_month(Month(2026, 9)),
        "$ 1.000,00",
        "$ 300,00",
        "$ 700,00",
        "70 %",
    ]
    assert table_row(view, 2)[4] == "—"  # no income in November


def test_cash_flow_compares_the_savings_rate_in_points(services, pesos, filled):
    services.transactions.create(income_draft(services, pesos.id, ars("1000"), date(2026, 8, 1)))
    services.transactions.create(expense_draft(services, pesos.id, ars("500"), date(2026, 8, 2)))
    view = cash_flow_view(filled)

    assert view.rate_badge.text() == "↗ 10 pp"  # 50 % in Jun-Aug, 60 % in Sep-Nov
    assert view.income_badge.text() == "→ 0 %"
    assert view.expenses_badge.text() == "↘ 20 %"


def test_cash_flow_month_opens_its_transactions(qtbot, filled):
    view = cash_flow_view(filled)
    october = Period.of_months(Month(2026, 10))

    with qtbot.waitSignal(filled.transactions_requested) as from_bar:
        view.chart.clicked.emit(1)
    assert from_bar.args == [TransactionFocus(october)]

    with qtbot.waitSignal(filled.transactions_requested) as from_row:
        view.table.doubleClicked.emit(view.model.index(1, 0))
    assert from_row.args == [TransactionFocus(october)]


def test_cash_flow_empty_period(page):
    view = cash_flow_view(page)

    assert view.chart.isHidden()
    assert not view.empty_label.isHidden()
    assert view.model.rowCount() == 3


# Net worth


def test_net_worth_month_ends_with_their_change(filled):
    view = net_worth_view(filled)

    assert not view.card.chart.isHidden()
    assert view.model.rowCount() == 3  # September, October and November so far
    september, october = table_row(view, 0), table_row(view, 1)
    assert september[0] == format_month(Month(2026, 9))
    assert september[4] == "+$ 700,00"  # from the end of August
    assert october[4] == "-$ 100,00"


def test_net_worth_table_follows_the_currency(services, dollars, filled):
    view = net_worth_view(filled)

    view.card.currency_input.set_index(1)

    assert view.model.headerData(3, Qt.Orientation.Horizontal) == "Total en US$"
    assert table_row(view, 0)[3] == NO_RATE_TEXT  # no exchange rate loaded
    assert table_row(view, 0)[4] == "—"


def test_net_worth_table_has_a_column_per_currency_held(services, dollars, movements, page):
    services.accounts.create("Europa", AccountType.CASH, Currency.EUR, eur("100"))
    page.refresh()
    view = net_worth_view(page)

    headers = [view.model.headerData(c, Qt.Orientation.Horizontal) for c in range(6)]

    assert headers == ["Mes", "En pesos", "En dólares", "En euros", "Total en $", "Variación"]
    assert table_row(view, 0)[3] == "€ 100,00"


def test_net_worth_asks_for_a_rate_in_settings(qtbot, page):
    view = net_worth_view(page)

    with qtbot.waitSignal(page.navigate_requested) as navigate:
        view.card.rate_requested.emit()
    assert navigate.args == [PageId.SETTINGS]
