"""An account kept out of every total, such as one shared with a band (plan 029, Fase D):
its movements count nowhere but in its own view, and money put into it leaves the net
worth without being spent."""

from datetime import timedelta

import pytest
from factories import TODAY, ars, category_id, charge_draft, expense_draft, income_draft

from nodus.models.account import AccountType
from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.models.period import Month, Period
from nodus.models.transaction import TransactionType
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.transactions.transfer_service import TransferDraft

MONTH = Period.of_months(Month.of(TODAY))
EXPENSE = TransactionType.EXPENSE


@pytest.fixture
def band(services):
    """The band's account, with $ 50.000 of its own."""
    return services.accounts.create(
        "Banda", AccountType.BANK, Currency.ARS, ars("50000"), excluded=True
    )


@pytest.fixture
def band_spending(services, pesos, band):
    """The user's own groceries, and the band's rehearsal room and a gig's pay, tagged
    and with payees, so every total has something to leave out."""
    food = services.transactions.create(
        expense_draft(services, pesos.id, ars("1000"), payee_name="Coto", tag_names=("Gira",))
    )
    room = services.transactions.create(
        expense_draft(services, band.id, ars("8000"), payee_name="Coto", tag_names=("Gira",))
    )
    gig = services.transactions.create(income_draft(services, band.id, ars("20000")))
    return food, room, gig


def test_the_account_is_marked_and_keeps_its_mark(services, band):
    assert services.accounts.get(band.id).excluded
    services.accounts.update(band.id, "Banda de rock", AccountType.BANK, ars("50000"))
    assert services.accounts.get(band.id).excluded  # editing the rest keeps it
    services.accounts.update(band.id, "Banda de rock", AccountType.BANK, ars("50000"), False)
    assert not services.accounts.get(band.id).excluded


def test_income_and_expenses_leave_it_out(services, band_spending):
    summary = services.dashboard.summary(MONTH)
    report = services.category_report.report(MONTH)
    flow = services.analysis.cash_flow(MONTH, TODAY)

    assert summary.income.is_zero
    assert summary.expenses == ars("1000")
    assert [section.total for section in report.sections] == [ars("1000"), ars("0")]
    assert (flow.current.income, flow.current.expenses) == (ars("0"), ars("1000"))
    food = category_id(services, "Supermercado y comida", EXPENSE)
    assert services.category_report.summary(food, TODAY).totals.net == ars("1000")


def test_payees_tags_and_budgets_leave_it_out(services, band_spending):
    food = category_id(services, "Supermercado y comida", EXPENSE)
    services.budgets.set_limit(food, Month.of(TODAY), ars("5000"))
    coto = services.payees.summaries(MONTH)[0]
    trip = services.tags.summaries(MONTH)[0]

    assert (coto.count, coto.totals.net) == (1, ars("-1000"))
    assert (trip.count, trip.totals.net) == (1, ars("-1000"))
    assert services.budgets.month_budgets(Month.of(TODAY), TODAY).budgets[0].spent == ars("1000")


def test_its_own_view_counts_everything(services, band, band_spending):
    """Transactions filtered by the band's account, and a selection there, show what
    came in and went out of it."""
    criteria = TransactionFilter(account_id=band.id)
    listed = services.transactions.list_transactions(criteria)

    totals = services.dashboard.totals(criteria)
    selected = services.dashboard.totals_of(listed, band.id)

    assert (totals.income, totals.expenses) == (ars("20000"), ars("8000"))
    assert (selected.income, selected.expenses) == (ars("20000"), ars("8000"))
    assert services.dashboard.totals_of(listed).expenses.is_zero  # in the whole list


def test_the_net_worth_and_the_totals_leave_it_out(services, pesos, band):
    net_worth = services.net_worth.net_worth(TODAY)
    accounts = [pesos, services.accounts.get(band.id)]
    balances = services.accounts.balances(TODAY)

    assert net_worth.total_in[HOME_CURRENCY] == ars("100000")
    assert services.account_groups.total(accounts, balances, TODAY).amount == ars("100000")
    history = services.net_worth.history(MONTH, TODAY)
    assert history[-1].net_worth.total_in[HOME_CURRENCY] == ars("100000")


def test_putting_money_in_lowers_the_net_worth_without_spending_it(services, pesos, band):
    """The contribution is a transfer: it leaves the user's hands, so the net worth
    drops, but no category or budget sees it."""
    yesterday = TODAY - timedelta(days=1)
    services.transfers.create(TransferDraft(pesos.id, band.id, ars("30000"), TODAY))

    before = services.net_worth.net_worth(yesterday).total_in[HOME_CURRENCY]
    after = services.net_worth.net_worth(TODAY).total_in[HOME_CURRENCY]

    assert (before, after) == (ars("100000"), ars("70000"))
    assert services.dashboard.summary(MONTH).expenses.is_zero
    assert services.accounts.balance(band.id) == ars("80000")


def test_its_recurring_charges_cost_the_user_nothing(services, pesos, band):
    services.recurring.create(charge_draft(services, pesos.id, ars("10000")))
    services.recurring.create(charge_draft(services, band.id, ars("40000"), name="Sala"))

    summary = services.recurring.summary(TODAY)

    assert (summary.monthly, summary.active) == (ars("10000"), 2)


def test_a_list_of_the_users_own_leaves_out_its_income_and_expenses(services, pesos, band):
    """As «Últimas transacciones» on Home lists them: the band's gig is not the user's,
    but the money they put into it left their hands, so that transfer stays."""
    services.transactions.create(expense_draft(services, pesos.id, ars("1000")))
    services.transactions.create(income_draft(services, band.id, ars("20000")))
    services.transfers.create(TransferDraft(pesos.id, band.id, ars("3000"), TODAY))

    own = services.transactions.list_transactions(TransactionFilter(own_only=True))

    assert sorted((t.account_id, t.amount, t.is_transfer) for t in own) == sorted(
        [
            (pesos.id, ars("1000"), False),
            (pesos.id, ars("3000"), True),
            (band.id, ars("3000"), True),
        ]
    )
