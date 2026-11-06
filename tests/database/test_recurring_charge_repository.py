"""Recurring charges keep their own currency and the rate of their last payment."""

import dataclasses
from datetime import date
from decimal import Decimal

from nodus.database.repositories.recurring_charge_repository import RecurringChargeRepository
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.recurring_charge import Frequency, RecurringCharge


def test_saves_currency_and_last_paid_rate(database, services, pesos):
    repository = RecurringChargeRepository(database)
    category_id = services.categories.list_categories()[0].id
    charge = RecurringCharge(
        None, "Suscripción", Money(10000, Currency.USD), pesos.id, category_id,
        Frequency.MONTHLY, 5, date(2026, 12, 5),
    )  # fmt: skip

    with database.transaction():
        saved = repository.add(charge)
    assert repository.get(saved.id) == saved
    assert repository.get(saved.id).amount.currency is Currency.USD

    paid = dataclasses.replace(saved, last_paid_rate=Decimal("1650.25"))
    with database.transaction():
        repository.update(paid)
    assert repository.get(saved.id).last_paid_rate == Decimal("1650.25")
