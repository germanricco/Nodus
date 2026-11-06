from datetime import date
from decimal import Decimal

import pytest
from factories import TODAY, ars, category_id, charge_draft, usd

from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import TransactionType
from nodus.services.errors import ValidationError


def create(services, account_id, amount, due=TODAY, **overrides):
    return services.recurring.create(charge_draft(services, account_id, amount, due, **overrides))


def test_create_sets_the_anchor_day_from_the_due_date(services, pesos):
    charge = create(services, pesos.id, ars("15000"), date(2026, 12, 31))

    assert charge.anchor_day == 31
    assert services.recurring.get(charge.id).amount == ars("15000")


@pytest.mark.parametrize(
    ("name", "amount", "message"),
    [
        ("  ", ars("100"), "nombre"),
        ("Internet", ars("0"), "mayor que cero"),
        ("Internet", usd("10"), "moneda"),
    ],
)
def test_create_validates_like_an_expense(services, pesos, name, amount, message):
    with pytest.raises(ValidationError, match=message):
        create(services, pesos.id, amount, name=name)


def test_create_rejects_an_income_category(services, pesos):
    salary = category_id(services, "Sueldo", TransactionType.INCOME)
    with pytest.raises(ValidationError, match="categoría"):
        create(services, pesos.id, ars("100"), category_id=salary)


def test_update_keeps_the_anchor_day_unless_the_schedule_changes(services, pesos):
    charge = create(services, pesos.id, ars("100"), date(2027, 1, 31))
    services.recurring.skip(charge.id)  # now due on 28/02, still anchored to the 31st

    services.recurring.update(
        charge.id, charge_draft(services, pesos.id, ars("120"), date(2027, 2, 28), name="Fibra")
    )
    assert services.recurring.get(charge.id).anchor_day == 31

    services.recurring.update(
        charge.id, charge_draft(services, pesos.id, ars("120"), date(2027, 3, 10))
    )
    assert services.recurring.get(charge.id).anchor_day == 10


def test_pay_records_the_expense_and_advances_from_the_due_date(services, pesos):
    charge = create(services, pesos.id, ars("15000"), date(2026, 10, 31))

    paid = services.recurring.pay(charge.id, ars("16200"), TODAY, pesos.id)

    assert paid.amount == ars("16200")
    assert paid.occurred_on == TODAY
    assert paid.note == "Internet"
    assert paid.category_id == charge.category_id
    assert services.accounts.balance(pesos.id) == ars("83800")
    # Paid late, but the calendar keeps the 30/11 that follows 31/10.
    assert services.recurring.get(charge.id).next_due_on == date(2026, 11, 30)


def test_pay_from_another_account(services, pesos):
    other = services.accounts.create("Efectivo", pesos.type, pesos.currency, ars("1000"))
    charge = create(services, pesos.id, ars("100"))

    services.recurring.pay(charge.id, ars("100"), TODAY, other.id)

    assert services.accounts.balance(other.id) == ars("900")


def test_a_failed_payment_leaves_the_charge_as_it_was(services, pesos, dollars):
    charge = create(services, pesos.id, ars("100"))

    with pytest.raises(ValidationError):
        services.recurring.pay(charge.id, ars("100"), TODAY, dollars.id)

    assert services.recurring.get(charge.id).next_due_on == TODAY
    assert services.accounts.balance(dollars.id) == usd("500")


def test_skip_advances_without_recording(services, pesos):
    charge = create(services, pesos.id, ars("100"))

    services.recurring.skip(charge.id)

    assert services.recurring.get(charge.id).next_due_on == date(2026, 12, 5)
    assert services.accounts.balance(pesos.id) == ars("100000")


def test_paused_charges_cannot_be_paid_and_leave_the_totals(services, pesos):
    charge = create(services, pesos.id, ars("100"))
    services.recurring.set_active(charge.id, False)

    with pytest.raises(ValidationError, match="pausa"):
        services.recurring.pay(charge.id, ars("100"), TODAY, pesos.id)
    assert services.recurring.summary(TODAY).active == 0
    assert services.recurring.upcoming(TODAY) == []

    services.recurring.set_active(charge.id, True)
    assert services.recurring.summary(TODAY).active == 1


def test_summary_converts_dollar_charges_at_the_latest_rate(services, pesos, dollars):
    create(services, pesos.id, ars("12000"))
    create(services, dollars.id, usd("120"), frequency=Frequency.ANNUAL)

    without_rate = services.recurring.summary(TODAY)
    assert without_rate.monthly == ars("12000")
    assert without_rate.unconverted_monthly == usd("10")

    services.exchange_rates.set_rate(date(2026, 11, 1), Decimal("1000"))
    summary = services.recurring.summary(TODAY)
    assert summary.monthly == ars("22000")
    assert summary.unconverted_monthly.is_zero
    assert summary.yearly == ars("264000")
    assert summary.active == 2


def test_upcoming_lists_overdue_first_and_stops_at_the_horizon(services, pesos):
    create(services, pesos.id, ars("1"), date(2026, 11, 25), name="Más tarde")
    create(services, pesos.id, ars("1"), date(2026, 11, 10), name="Pronto")
    create(services, pesos.id, ars("1"), date(2026, 11, 1), name="Vencido")

    names = [c.name for c in services.recurring.upcoming(TODAY)]

    assert names == ["Vencido", "Pronto"]


def test_deleting_a_category_moves_its_charges_to_otros(services, pesos):
    gym = services.categories.create("Gimnasio", TransactionType.EXPENSE, "#123456")
    charge = create(services, pesos.id, ars("100"), category_id=gym.id)

    services.categories.delete(gym.id)

    otros = category_id(services, "Otros", TransactionType.EXPENSE)
    assert services.recurring.get(charge.id).category_id == otros


def test_deleting_an_account_deletes_its_charges(services, pesos):
    charge = create(services, pesos.id, ars("100"))
    assert services.recurring.count_for_account(pesos.id) == 1

    services.accounts.delete(pesos.id)

    assert services.recurring.list_charges() == []
    with pytest.raises(ValidationError):
        services.recurring.get(charge.id)
