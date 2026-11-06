from datetime import date

from factories import ars, expense_draft, income_draft
from PySide6.QtWidgets import QLabel

from nodus.models.period import Month, Period
from nodus.ui.navigation import PageId
from nodus.ui.pages.dashboard_page import LatestTransactionRow, percent
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
    qtbot.waitUntil(lambda: "$ 750,00" in visible_texts(page))
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
