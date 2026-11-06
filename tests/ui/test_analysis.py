"""The analysis page and its reports."""

from datetime import date

import pytest
from factories import ars, category_id, expense_draft, income_draft

from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.ui.navigation import PageId
from nodus.ui.pages.analysis_page import AnalysisPage
from nodus.ui.pages.analysis_views import NO_PAYEE_LABEL, TrendsView

EXPENSE = TransactionType.EXPENSE
SEP_NOV = Period.of_months(Month(2026, 9), Month(2026, 11))
SAVINGS_TAB = 2


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
    assert from_bar.args == [Period.of_months(Month(2026, 10)), servicios, None]

    with qtbot.waitSignal(page.transactions_requested) as from_payee:
        view._payee_rows.itemAt(0).widget().clicked.emit()
    assert from_payee.args == [SEP_NOV, None, services.payees.find("Coto").id]


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
