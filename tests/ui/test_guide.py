"""Primeros pasos on Inicio: each step's button leads to it, and the card steps aside."""

import dataclasses

import pytest
from factories import ars, expense_draft
from PySide6.QtWidgets import QLabel

from nodus.services.guide_service import GuideStepKind
from nodus.ui import main_window
from nodus.ui.navigation import PageId
from nodus.ui.pages import dashboard_page
from nodus.ui.pages.guide_card import DONE_TEXT


def dashboard(window):
    page = window.page(PageId.DASHBOARD)
    window.show_page(PageId.DASHBOARD)
    return page


@pytest.fixture
def opened(monkeypatch) -> list[str]:
    """The forms the steps open, by class name, instead of showing them."""
    names = []
    for name in ("AccountDialog", "RecurringChargeDialog", "BudgetDialog", "GoalDialog"):
        monkeypatch.setattr(
            getattr(dashboard_page, name), "exec", lambda self, n=name: names.append(n)
        )
    monkeypatch.setattr(
        main_window.TransactionDialog, "exec", lambda self: names.append("TransactionDialog")
    )
    monkeypatch.setattr(
        dashboard_page, "save_copy_outside", lambda *args: names.append("save_copy_outside")
    )
    return names


def test_before_the_first_account_the_guide_is_the_welcome(window, opened):
    page = dashboard(window)

    assert page.welcome_guide.isVisible()
    assert not page._welcome.isVisible()
    button = page.welcome_guide.buttons[GuideStepKind.ACCOUNT]
    assert button.objectName() == "PrimaryButton"
    button.click()
    assert opened == ["AccountDialog"]


def test_with_an_account_it_goes_first_and_across(window, pesos):
    page = dashboard(window)

    assert page.guide_card.isVisible()
    assert page._grid.getItemPosition(page._grid.indexOf(page.guide_card)) == (0, 0, 1, 6)
    assert page.guide_card.count_label.text() == "1 de 6"
    assert GuideStepKind.ACCOUNT not in page.guide_card.buttons
    assert page.guide_card.buttons[GuideStepKind.EXPENSE].objectName() == "PrimaryButton"


def test_every_step_opens_what_does_it(window, pesos, opened):
    page = dashboard(window)

    for kind in [k for k in GuideStepKind if k is not GuideStepKind.ACCOUNT]:
        page.guide_card.buttons[kind].click()

    assert opened == [
        "TransactionDialog",
        "RecurringChargeDialog",
        "BudgetDialog",
        "GoalDialog",
        "save_copy_outside",
    ]


def test_a_step_done_elsewhere_ticks_itself(window, services, event_bus, pesos):
    page = dashboard(window)

    services.transactions.create(expense_draft(services, pesos.id, ars("10")))
    event_bus.transactions_changed.emit()

    assert page.guide_card.count_label.text() == "2 de 6"
    assert GuideStepKind.EXPENSE not in page.guide_card.buttons


def test_hiding_asks_first(window, services, pesos, monkeypatch):
    page = dashboard(window)
    answers = iter([False, True])
    monkeypatch.setattr(dashboard_page, "ask", lambda *args: next(answers))

    page.guide_card.hide_button.click()
    assert page.guide_card.isVisible()

    page.guide_card.hide_button.click()
    assert not page.guide_card.isVisible()
    assert services.settings.guide_dismissed()


def test_all_done_says_so_and_closes_without_asking(window, services, pesos, monkeypatch):
    page = dashboard(window)
    every_step = services.guide.steps
    monkeypatch.setattr(
        services.guide,
        "steps",
        lambda today: [dataclasses.replace(step, done=True) for step in every_step(today)],
    )
    monkeypatch.setattr(dashboard_page, "ask", lambda *args: pytest.fail("asked"))
    page.refresh()

    texts = [label.text() for label in page.guide_card.findChildren(QLabel)]
    assert DONE_TEXT in texts
    assert page.guide_card.count_label.text() == "6 de 6"
    page.guide_card.close_button.click()

    assert services.settings.guide_dismissed()
    assert not page.guide_card.isVisible()
