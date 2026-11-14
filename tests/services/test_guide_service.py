"""Primeros pasos tick themselves off from the data and step aside for seasoned users."""

from datetime import date, timedelta

from factories import (
    TODAY,
    ars,
    category_id,
    charge_draft,
    data_since,
    expense_draft,
    income_draft,
    usd,
)

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.goal import GoalShare
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.services.goal_service import GoalDraft
from nodus.services.guide_service import NEW_USER_DAYS, GuideStepKind
from nodus.services.transaction_service import TransferDraft


def done(services) -> set[GuideStepKind]:
    return {step.kind for step in services.guide.steps(TODAY) if step.done}


def test_a_new_user_has_every_step_ahead(services):
    steps = services.guide.steps(TODAY)

    assert [step.kind for step in steps] == list(GuideStepKind)
    assert not any(step.done for step in steps)
    assert steps[0].title == "Crea tu primera cuenta"
    assert all(step.title for step in steps)


def test_each_step_ticks_itself_off(services, pesos, tmp_path):
    assert done(services) == {GuideStepKind.ACCOUNT}

    services.transactions.create(expense_draft(services, pesos.id, ars("10")))
    services.recurring.create(charge_draft(services, pesos.id, ars("9000")))
    services.budgets.set_limit(
        category_id(services, "Servicios", TransactionType.EXPENSE), Month.of(TODAY), ars("1")
    )
    savings = services.accounts.create("Ahorro", AccountType.SAVINGS, Currency.USD, usd("5"))
    services.goals.create(
        GoalDraft("Viaje", usd("100"), date(2027, 3, 31), (GoalShare(savings.id, 100),)), TODAY
    )
    services.settings.set_external_backup(TODAY, tmp_path)

    assert done(services) == set(GuideStepKind)


def test_an_income_or_a_transfer_is_not_an_expense(services, pesos):
    other = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("0"))
    services.transactions.create(income_draft(services, pesos.id, ars("10")))
    services.transactions.create_transfer(TransferDraft(pesos.id, other.id, ars("5"), TODAY))

    assert GuideStepKind.EXPENSE not in done(services)


def test_shown_to_whoever_starts_until_put_away(services, pesos):
    assert services.guide.visible(TODAY)

    services.guide.dismiss()
    assert not services.guide.visible(TODAY)

    services.guide.restore()
    assert services.guide.visible(TODAY)


def test_shown_before_the_first_account(services):
    assert services.guide.visible(TODAY)


def test_seasoned_data_does_not_get_the_list(services, database, pesos):
    data_since(database, TODAY - timedelta(days=NEW_USER_DAYS))

    assert not services.guide.visible(TODAY)
    assert services.guide.visible(TODAY - timedelta(days=1))
