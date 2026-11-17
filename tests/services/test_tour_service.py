"""The guided tour is offered once, to whoever already has an account."""

from factories import ars

from nodus.models.account import AccountType
from nodus.models.currency import Currency


def test_the_tour_waits_for_an_account_and_is_offered_once(services):
    assert not services.tour.tour_due()

    services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("0"))
    assert services.tour.tour_due()

    services.tour.mark_tour_offered()
    assert not services.tour.tour_due()
