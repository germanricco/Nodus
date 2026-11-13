from datetime import date
from decimal import Decimal

import pytest
from factories import ars, data_since, expense_draft, income_draft, usd

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.goal import GoalShare, GoalState
from nodus.services.errors import ValidationError
from nodus.services.goal_service import GoalDraft

TODAY = date(2026, 11, 13)


@pytest.fixture
def goals(services):
    return services.goals


@pytest.fixture
def savings(services, database):
    """A dollar savings account with US$ 500, with data since January."""
    account = services.accounts.create("Ahorro", AccountType.SAVINGS, Currency.USD, usd("500"))
    data_since(database, date(2026, 1, 10))
    return account


def draft(*shares, target="2000", on=date(2027, 3, 31), name="Vacaciones") -> GoalDraft:
    return GoalDraft(name, usd(target), on, tuple(GoalShare(a.id, p) for a, p in shares))


class TestRules:
    def test_created_with_its_shares(self, goals, savings):
        goal = goals.create(draft((savings, 100)), TODAY)

        assert goals.get(goal.id).shares == (GoalShare(savings.id, 100),)
        assert [g.name for g in goals.list_goals()] == ["Vacaciones"]

    @pytest.mark.parametrize(
        ("changes", "field"),
        [
            ({"name": "  "}, "name"),
            ({"target": usd("0")}, "target"),
            ({"target_date": TODAY}, "target_date"),
            ({"shares": ()}, "shares"),
        ],
    )
    def test_rejects(self, goals, savings, changes, field):
        values = draft((savings, 100)).__dict__ | changes
        with pytest.raises(ValidationError) as error:
            goals.create(GoalDraft(**values), TODAY)
        assert error.value.field == field

    def test_a_card_cannot_fill_a_goal(self, services, goals):
        visa = services.accounts.create("Visa", AccountType.CREDIT_CARD, Currency.ARS, ars("0"))

        with pytest.raises(ValidationError, match="tarjeta"):
            goals.create(draft((visa, 100)), TODAY)

    def test_an_account_is_shared_up_to_a_hundred_percent(self, goals, savings):
        goals.create(draft((savings, 60)), TODAY)
        assert goals.free_percent(savings.id) == 40

        with pytest.raises(
            ValidationError, match="«Ahorro» ya tiene 60 % en «Vacaciones»: quedan 40 %."
        ):
            goals.create(draft((savings, 41), name="Auto"), TODAY)
        goals.create(draft((savings, 40), name="Auto"), TODAY)

    def test_its_own_share_does_not_count_against_it(self, goals, savings):
        goal = goals.create(draft((savings, 100)), TODAY)

        goals.update(goal.id, draft((savings, 100), target="3000"), TODAY)

        assert goals.get(goal.id).target == usd("3000")

    def test_archiving_frees_the_share_and_unarchiving_needs_it_back(self, goals, savings):
        old = goals.create(draft((savings, 100)), TODAY)
        goals.set_archived(old.id, True)
        goals.create(draft((savings, 100), name="Auto"), TODAY)

        with pytest.raises(ValidationError):
            goals.set_archived(old.id, False)

    def test_deleting_an_account_takes_it_out_of_the_goal(self, services, goals, savings):
        cash = services.accounts.create("Caja", AccountType.CASH, Currency.USD, usd("10"))
        goal = goals.create(draft((savings, 100), (cash, 100)), TODAY)

        services.accounts.delete(cash.id)

        assert goals.get(goal.id).shares == (GoalShare(savings.id, 100),)

    def test_deleting_a_goal_keeps_the_accounts(self, services, goals, savings):
        goal = goals.create(draft((savings, 100)), TODAY)

        goals.delete(goal.id)

        assert goals.list_goals() == []
        assert services.accounts.balance(savings.id, TODAY) == usd("500")

    def test_eligible_accounts_leave_out_cards_and_archived_ones(self, services, goals, savings):
        services.accounts.create("Visa", AccountType.CREDIT_CARD, Currency.ARS, ars("0"))
        old = services.accounts.create("Vieja", AccountType.BANK, Currency.ARS, ars("0"))
        services.accounts.set_archived(old.id, True)

        assert [a.name for a in goals.eligible_accounts()] == ["Ahorro"]


class TestProgress:
    def test_saved_is_the_share_of_the_balance(self, goals, savings):
        goal = goals.create(draft((savings, 60)), TODAY)

        assert goals.saved_on(goal, TODAY, TODAY) == usd("300")

    def test_other_currencies_count_at_todays_rate(self, services, goals, savings):
        pesos = services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("100000"))
        goal = goals.create(draft((savings, 100), (pesos, 50)), TODAY)
        assert goals.progress(goals.get(goal.id), TODAY).state is GoalState.NO_RATE

        services.exchange_rates.set_rate(TODAY, Decimal("1000"))

        assert goals.saved_on(goal, TODAY, TODAY) == usd("550")

    def test_a_negative_balance_takes_nothing_away(self, services, goals, savings):
        cash = services.accounts.create("Caja", AccountType.CASH, Currency.USD, usd("0"))
        services.transactions.create(expense_draft(services, cash.id, usd("50"), on=TODAY))
        goal = goals.create(draft((savings, 100), (cash, 100)), TODAY)

        assert goals.saved_on(goal, TODAY, TODAY) == usd("500")

    def test_the_pace_comes_from_the_month_ends(self, services, goals, savings):
        for month in (7, 8, 9, 10):
            services.transactions.create(
                income_draft(services, savings.id, usd("300"), on=date(2026, month, 15))
            )
        goal = goals.create(draft((savings, 100)), TODAY)

        progress = goals.progress(goal, TODAY)

        assert progress.pace_per_month == usd("300")
        assert progress.saved == usd("1700")
        assert progress.state is GoalState.ON_TRACK  # 300 a month covers 300 in 1 month

    def test_month_ends_start_when_the_accounts_have_data(self, services, database, goals, savings):
        data_since(database, date(2026, 9, 20))
        goal = goals.create(draft((savings, 100)), TODAY)

        assert [day for day, _saved in goals.month_ends(goal, TODAY, 12)] == [
            date(2026, 9, 30),
            date(2026, 10, 31),
        ]
        assert goals.progress(goal, TODAY).state is GoalState.NO_HISTORY

    def test_contributions(self, services, goals, savings):
        goal = goals.create(draft((savings, 60)), TODAY)

        [contribution] = goals.contributions(goal, TODAY)

        assert (contribution.account.name, contribution.percent) == ("Ahorro", 60)
        assert (contribution.balance, contribution.counted) == (usd("500"), usd("300"))

    def test_goals_for_an_account(self, goals, savings):
        goals.create(draft((savings, 60)), TODAY)
        archived = goals.create(draft((savings, 40), name="Auto"), TODAY)
        goals.set_archived(archived.id, True)

        assert [(g.name, p) for g, p in goals.goals_for_account(savings.id)] == [("Vacaciones", 60)]


class TestReached:
    def test_reached_once_and_announced_until_seen(self, services, goals, savings):
        goal = goals.create(draft((savings, 100), target="600"), TODAY)
        assert goals.check_reached(TODAY) == []

        services.transactions.create(income_draft(services, savings.id, usd("100"), on=TODAY))
        [reached] = goals.check_reached(TODAY)

        assert reached.reached_on == TODAY
        assert goals.check_reached(TODAY) == []
        assert [g.id for g in goals.unseen_reached()] == [goal.id]
        goals.mark_seen(goal.id)
        assert goals.unseen_reached() == []

    def test_stays_reached_when_spent_until_the_target_changes(self, services, goals, savings):
        goal = goals.create(draft((savings, 100), target="500"), TODAY)
        goals.check_reached(TODAY)
        services.transactions.create(expense_draft(services, savings.id, usd("400"), on=TODAY))

        assert goals.progress(goals.get(goal.id), TODAY).state is GoalState.REACHED

        goals.update(goal.id, draft((savings, 100), target="900"), TODAY)

        updated = goals.get(goal.id)
        assert updated.reached_on is None
        assert goals.progress(updated, TODAY).state is not GoalState.REACHED

    def test_editing_the_name_keeps_it_reached(self, goals, savings):
        goal = goals.create(draft((savings, 100), target="500"), TODAY)
        goals.check_reached(TODAY)

        goals.update(goal.id, draft((savings, 100), target="500", name="Brasil"), TODAY)

        assert goals.get(goal.id).reached_on == TODAY
