"""Every row answers the same way on every page: its main action is bold in its menu and
runs on a double click, and its light goes off when a menu closes elsewhere."""

from datetime import date
from decimal import Decimal

from factories import TODAY, ars, charge_draft, expense_draft
from menus import double_click, double_click_row, main_action
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu, QWidget

from nodus.models.currency import Currency
from nodus.models.exchange_rate import ExchangeRate
from nodus.ui.navigation import PageId
from nodus.ui.pages.categories_page import CategoriesPage, CategoryRow
from nodus.ui.pages.recurring_page import RecurringChargeRow
from nodus.ui.pages.settings_page import RateRow
from nodus.ui.widgets.row_actions import RowAction, build_menu, install_row_actions

FAR_AWAY = QPoint(5000, 5000)


def category_rows(qtbot, services, event_bus) -> list[CategoryRow]:
    page = CategoriesPage(services, event_bus)
    qtbot.addWidget(page)
    page.refresh()
    page.show()
    return [row for row in page.findChildren(CategoryRow) if row.isVisible()]


def test_the_main_action_is_bold_in_the_menu(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    actions = [
        RowAction("Abrir", lambda: None),
        RowAction("Editar", lambda: None, default=True),
        RowAction("Eliminar", lambda: None, destructive=True),
    ]

    menu = build_menu(parent, actions)

    assert menu.defaultAction().text() == "Editar"


def test_a_double_click_on_a_category_edits_it(qtbot, services, event_bus):
    rows = category_rows(qtbot, services, event_bus)
    row = next(r for r in rows if not r.category.is_system)
    edited = []
    row.edit_requested.disconnect()  # the page would open its dialog
    row.edit_requested.connect(edited.append)

    double_click(row)

    assert edited == [row.category]
    assert main_action(row.actions()) == "Editar"


def test_otros_cannot_change_so_its_main_action_shows_its_movements(qtbot, services, event_bus):
    rows = category_rows(qtbot, services, event_bus)
    otros = next(r for r in rows if r.category.is_system)

    assert main_action(otros.actions()) == "Ver movimientos"


def test_a_charge_is_paid_with_a_double_click_and_a_paused_one_edited(services, pesos, qtbot):
    charge = services.recurring.create(charge_draft(services, pesos.id, ars("10"), TODAY))
    category = services.categories.get(charge.category_id)
    row = RecurringChargeRow(charge, category, "Banco", TODAY)
    qtbot.addWidget(row)
    row.show()
    paid = []
    row.pay_requested.connect(paid.append)

    double_click(row)

    assert paid == [charge]
    services.recurring.set_active(charge.id, False)
    paused = RecurringChargeRow(services.recurring.get(charge.id), category, "Banco", TODAY)
    assert main_action(paused.actions()) == "Editar"


def test_a_row_whose_only_action_deletes_has_no_main_action():
    rate = ExchangeRate(1, date(2026, 11, 1), Currency.USD, Currency.ARS, Decimal("1000"))
    assert main_action(RateRow(rate).actions()) is None


def test_a_double_click_on_a_transaction_edits_it(window, services, pesos, monkeypatch):
    services.transactions.create(expense_draft(services, pesos.id, ars("10")))
    window.show_page(PageId.TRANSACTIONS)
    view = window.page(PageId.TRANSACTIONS).list_view
    edited = []
    monkeypatch.setattr(view, "edit", edited.append)

    double_click_row(view.table, 0)

    assert [item.description for item in edited] == [view.model.item(0).description]
    assert view.table.selected_rows() == [0]


def test_a_row_turns_its_light_off_when_its_menu_closes_elsewhere(qtbot):
    row = QWidget()
    qtbot.addWidget(row)
    install_row_actions(row, lambda: [RowAction("Editar", lambda: None, default=True)])
    row.resize(200, 40)
    row.show()
    row.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)

    row.customContextMenuRequested.emit(QPoint(5, 5))
    QCursor.setPos(FAR_AWAY)
    for menu in row.findChildren(QMenu):
        menu.close()

    assert not row.testAttribute(Qt.WidgetAttribute.WA_UnderMouse)


def test_a_table_turns_its_light_off_when_its_menu_closes_elsewhere(window, services, pesos):
    services.transactions.create(expense_draft(services, pesos.id, ars("10")))
    window.show_page(PageId.TRANSACTIONS)
    table = window.page(PageId.TRANSACTIONS).list_view.table
    table.hovered_row = 0

    table.open_menu(0, table.viewport().mapToGlobal(QPoint(5, 5)))
    QCursor.setPos(FAR_AWAY)
    for menu in table.findChildren(QMenu):
        menu.close()

    assert table.hovered_row == -1
