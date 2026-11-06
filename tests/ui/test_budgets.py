from datetime import date

import pytest
from factories import TODAY, ars, category_id, expense_draft
from PySide6.QtCore import Qt

from nodus.models.budget import BudgetState
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.ui.dialogs.budget_dialog import BudgetDialog
from nodus.ui.navigation import PageId, TransactionFocus
from nodus.ui.pages import budgets_page
from nodus.ui.pages.budgets_page import BudgetsPage

NOVEMBER = Month.of(TODAY)


def expense(name: str, services) -> int:
    return category_id(services, name, TransactionType.EXPENSE)


def spend(services, account_id, amount, category, on=TODAY):
    services.transactions.create(
        expense_draft(services, account_id, ars(amount), on, category_id=category)
    )


@pytest.fixture
def page(qtbot, services, event_bus, theme_manager) -> BudgetsPage:
    budgets = BudgetsPage(services, event_bus, theme_manager)
    qtbot.addWidget(budgets)
    budgets.show_month(NOVEMBER)
    budgets.refresh(TODAY)
    return budgets


class TestDialog:
    def test_creates_a_budget_from_the_month_shown(self, qtbot, services, event_bus, pesos):
        food = expense("Supermercado y comida", services)
        dialog = BudgetDialog(services, event_bus, NOVEMBER)
        qtbot.addWidget(dialog)
        dialog.category_input.select(food)
        dialog.amount_input.line_edit.setText("400.000")

        with qtbot.waitSignal(event_bus.budgets_changed):
            qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

        assert services.budgets.limits_on(NOVEMBER) == {food: ars("400000")}
        assert services.budgets.limits_on(NOVEMBER.previous()) == {}

    def test_offers_only_categories_without_a_budget(self, qtbot, services, event_bus):
        food = expense("Supermercado y comida", services)
        services.budgets.set_limit(food, NOVEMBER, ars("100"))

        dialog = BudgetDialog(services, event_bus, NOVEMBER)
        qtbot.addWidget(dialog)

        ids = {dialog.category_input.itemData(i) for i in range(dialog.category_input.count())}
        assert food not in ids
        assert expense("Ocio", services) in ids

    def test_suggests_the_recent_average(self, qtbot, services, event_bus, pesos):
        leisure = expense("Ocio", services)
        for month in (8, 9, 10):
            spend(services, pesos.id, "30000", leisure, on=date(2026, month, 3))

        dialog = BudgetDialog(services, event_bus, NOVEMBER, services.categories.get(leisure))
        qtbot.addWidget(dialog)

        assert dialog.amount_input.money() == ars("30000")
        assert "$ 30.000,00" in dialog.suggestion_hint.text()
        assert dialog.windowTitle() == "Nuevo presupuesto"

    def test_changing_a_limit_starts_from_the_current_one(self, qtbot, services, event_bus):
        food = expense("Supermercado y comida", services)
        services.budgets.set_limit(food, NOVEMBER, ars("250000"))

        dialog = BudgetDialog(services, event_bus, NOVEMBER, services.categories.get(food))
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == "Cambiar límite"
        assert dialog.amount_input.money() == ars("250000")
        assert not dialog.category_input.isEnabled()


class TestPage:
    def test_empty_state(self, page):
        assert page.rows == []

    def test_shows_budgets_by_use_with_totals(self, qtbot, services, event_bus, pesos, page):
        food, leisure = expense("Supermercado y comida", services), expense("Ocio", services)
        services.budgets.set_limit(food, NOVEMBER, ars("1000"))
        services.budgets.set_limit(leisure, NOVEMBER, ars("100"))
        spend(services, pesos.id, "200", food)
        spend(services, pesos.id, "150", leisure)
        spend(services, pesos.id, "50", expense("Transporte", services))

        event_bus.budgets_changed.emit()

        over, ok = page.rows
        assert over.budget.category.name == "Ocio"
        assert over.budget.state is BudgetState.OVER
        assert over.pill.text() == "Excedido en $ 50,00"
        assert ok.usage_label.text() == "20 % usado · $ 200,00 de $ 1.000,00"
        assert ok.pill.text() == "Quedan $ 800,00"
        assert page.limit_label.text() == "$ 1.100,00"
        assert page.remaining_label.text() == "$ 750,00"
        assert [line.name for line in page.unbudgeted_rows] == ["Transporte"]

    def test_each_month_shows_its_own_limit(self, services, event_bus, page):
        food = expense("Supermercado y comida", services)
        services.budgets.set_limit(food, NOVEMBER.previous(), ars("300"))
        services.budgets.set_limit(food, NOVEMBER, ars("500"))

        page.refresh(TODAY)
        assert page.rows[0].budget.limit == ars("500")

        page.month_selector.previous_button.click()
        assert page.rows[0].budget.limit == ars("300")

    def test_pace_mark_only_in_the_current_month(self, services, page):
        services.budgets.set_limit(expense("Ocio", services), NOVEMBER.previous(), ars("100"))
        page.refresh(TODAY)
        assert page.rows[0].bar.shows_pace

        page.show_month(NOVEMBER.previous())

        assert not page.rows[0].bar.shows_pace

    def test_remove_keeps_earlier_months(self, services, page, monkeypatch):
        food = expense("Supermercado y comida", services)
        services.budgets.set_limit(food, NOVEMBER.previous(), ars("300"))
        page.refresh(TODAY)
        monkeypatch.setattr(budgets_page, "confirm", lambda *_args, **_kwargs: True)

        page.rows[0].remove_requested.emit()

        assert page.rows == []
        assert services.budgets.limits_on(NOVEMBER.previous()) == {food: ars("300")}

    def test_clicking_a_row_opens_its_transactions(self, qtbot, services, page):
        food = expense("Supermercado y comida", services)
        services.budgets.set_limit(food, NOVEMBER, ars("300"))
        page.refresh(TODAY)

        with qtbot.waitSignal(page.transactions_requested) as signal:
            qtbot.mouseClick(page.rows[0].line, Qt.MouseButton.LeftButton)

        assert signal.args == [TransactionFocus(Period.of_months(NOVEMBER), food)]


def test_page_is_in_the_sidebar(window):
    window.show_page(PageId.BUDGETS)

    assert isinstance(window.current_page, BudgetsPage)
