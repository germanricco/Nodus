"""Every page shows every change while it is in view, and only the page in view refreshes.

The table crosses each page, and each item's own page, with each change; a page that
listed by hand the changes it shows once missed some, and showed old data until it was
opened again.
"""

from __future__ import annotations

from datetime import date

import pytest
from factories import ars, expense_draft, usd
from PySide6.QtCore import QCoreApplication, QEvent, Signal
from PySide6.QtWidgets import QLabel

from nodus.models.goal import GoalShare
from nodus.models.transaction import TransactionType
from nodus.services.planning.goal_service import GoalDraft
from nodus.ui.event_bus import EventBus
from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages.categories_page import CategoryRow
from nodus.ui.refresh import screen_signals
from nodus.ui.theme.theme import ThemeMode

CHANGES = [
    "accounts_changed",
    "categories_changed",
    "transactions_changed",
    "exchange_rates_changed",
    "recurring_changed",
    "budgets_changed",
    "payees_changed",
    "tags_changed",
    "goals_changed",
    "backups_changed",
    "amounts_hidden_changed",
    "net_worth_currency_changed",
]


def emit(event_bus, change: str) -> None:
    signal = getattr(event_bus, change)
    if change == "amounts_hidden_changed":
        signal.emit(False)
    else:
        signal.emit()


@pytest.fixture
def items(services, pesos) -> dict[DetailId, int]:
    """One item for each detail page."""
    expense = services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), payee_name="Kiosco", tag_names=("Viaje",))
    )
    goal = services.goals.create(
        GoalDraft("Auto", usd("1000"), None, (GoalShare(pesos.id, 100),)), date.today()
    )
    return {
        DetailId.ACCOUNT: pesos.id,
        DetailId.CATEGORY: expense.category_id,
        DetailId.PAYEE: expense.payee_id,
        DetailId.TAG: services.tags.list_tags()[0].id,
        DetailId.GOAL: goal.id,
    }


def count_refreshes(monkeypatch, page) -> list[int]:
    calls: list[int] = []
    original = page.refresh
    monkeypatch.setattr(page, "refresh", lambda *a, **k: calls.append(1) or original(*a, **k))
    return calls


def test_every_signal_of_the_bus_is_a_change_the_screen_follows():
    """A signal added to the bus is followed by the screen and crossed with every page
    below, or this fails."""
    signals = {name for name, value in vars(EventBus).items() if isinstance(value, Signal)}
    bus = EventBus()

    assert signals == set(CHANGES)
    assert screen_signals(bus) == [getattr(bus, name) for name in CHANGES]


@pytest.mark.parametrize("change", CHANGES)
@pytest.mark.parametrize("page_id", list(PageId), ids=lambda p: p.name)
def test_the_page_in_view_shows_every_change(
    qtbot, monkeypatch, window, event_bus, pesos, page_id, change
):
    window.show_page(page_id)
    calls = count_refreshes(monkeypatch, window.page(page_id))

    emit(event_bus, change)

    assert calls


@pytest.mark.parametrize("change", CHANGES)
@pytest.mark.parametrize("detail_id", list(DetailId), ids=lambda d: d.name)
def test_the_item_page_in_view_shows_every_change(
    qtbot, monkeypatch, window, event_bus, items, detail_id, change
):
    window.show_detail(detail_id, items[detail_id])
    calls = count_refreshes(monkeypatch, window.detail(detail_id))

    emit(event_bus, change)

    assert calls


def test_a_page_out_of_view_waits_until_it_is_shown(qtbot, monkeypatch, window, event_bus):
    window.show_page(PageId.ANALYSIS)
    window.show_page(PageId.DASHBOARD)
    calls = count_refreshes(monkeypatch, window.page(PageId.ANALYSIS))

    event_bus.transactions_changed.emit()
    assert not calls

    window.show_page(PageId.ANALYSIS)
    assert calls


@pytest.mark.parametrize("page_id", [PageId.BUDGETS, PageId.GOALS, PageId.DASHBOARD])
def test_a_new_theme_repaints_the_page_in_view(qtbot, monkeypatch, window, theme_manager, page_id):
    window.show_page(page_id)
    calls = count_refreshes(monkeypatch, window.page(page_id))

    theme_manager.set_mode(ThemeMode.DARK)

    assert calls


def test_a_change_made_anywhere_reaches_the_sidebar(qtbot, window, services, event_bus, pesos):
    window.show_page(PageId.SETTINGS)
    services.transactions.create(expense_draft(services, pesos.id, ars("1000")))

    event_bus.transactions_changed.emit()

    texts = [label.text() for label in window.sidebar.findChildren(QLabel)]
    assert any("99.000" in text for text in texts)
    assert not any("100.000" in text for text in texts)


def test_a_change_made_anywhere_reaches_the_bell(qtbot, monkeypatch, window, event_bus):
    window.show_page(PageId.SETTINGS)
    counted: list[int] = []
    monkeypatch.setattr(window.top_bar, "set_notification_count", counted.append)

    event_bus.budgets_changed.emit()

    assert counted


def test_categories_offers_the_movements_of_a_first_transaction(
    qtbot, window, services, event_bus, pesos
):
    """Recorded from «Agregar transacción» while Categorías is in view, the movement of
    a category that had none is offered at once, not after opening the page again."""
    window.show_page(PageId.CATEGORIES)
    category = services.categories.create("Viajes", TransactionType.EXPENSE, "#123456")
    event_bus.categories_changed.emit()
    services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), category_id=category.id)
    )

    event_bus.transactions_changed.emit()

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)  # rows replaced
    rows = window.page(PageId.CATEGORIES).findChildren(CategoryRow)
    (row,) = [r for r in rows if r.category.id == category.id]
    assert row.has_movements
