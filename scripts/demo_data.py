"""Sample data for screenshots and manual testing. Never loaded into real user data."""

import random
from datetime import date, timedelta
from decimal import Decimal

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.services.recurring_charge_service import RecurringChargeDraft
from nodus.services.transaction_service import TransactionDraft, TransferDraft

# Months of history before the current one, so the dashboard has trends to show.
HISTORY_MONTHS = 5


def ars(amount: str | int) -> Money:
    return Money.from_decimal(str(amount), Currency.ARS)


def usd(amount: str | int) -> Money:
    return Money.from_decimal(str(amount), Currency.USD)


def load_demo_data(services: Services, today: date) -> None:
    """Creates a few accounts, monthly dollar rates, five months of typical movements and
    the current month's, with one month of overspending for contrast."""
    categories = {(c.kind, c.name): c.id for c in services.categories.list_categories()}
    income, expense = TransactionType.INCOME, TransactionType.EXPENSE
    alquiler = services.categories.create(
        "Alquiler", expense, "#e67e22", parent_id=categories[(expense, "Vivienda")]
    )
    categories[(expense, "Alquiler")] = alquiler.id

    def record(account_id, kind, category, amount, day, note=""):
        services.transactions.create(
            TransactionDraft(account_id, kind, amount, day, categories[(kind, category)], note)
        )

    banco = services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("420000"))
    efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("60000"))
    ahorro = services.accounts.create("Ahorro en dólares", AccountType.SAVINGS, Currency.USD,
                                      usd("400"))  # fmt: skip

    current = Month.of(today)
    random_ = random.Random(7)
    for back in range(HISTORY_MONTHS, 0, -1):
        month = current.shifted(-back)
        rate = Decimal(1215) - Decimal(32) * back
        services.exchange_rates.set_rate(month.start, rate)

        def on(day: int, month=month) -> date:
            return date(month.year, month.month, min(day, month.end.day))

        salary = 1_300_000 + 25_000 * (HISTORY_MONTHS - back)
        record(banco.id, income, "Sueldo", ars(salary), on(3), "Sueldo del mes")
        if back % 2 == 0:
            record(banco.id, income, "Trabajo freelance", ars(random_.randrange(150, 320) * 1000),
                   on(18), "Proyecto freelance")  # fmt: skip
        record(banco.id, expense, "Alquiler", ars(380_000 + 8_000 * (HISTORY_MONTHS - back)),
               on(5), "Alquiler")  # fmt: skip
        record(banco.id, expense, "Servicios", ars(random_.randrange(32, 48) * 1000), on(10),
               "Luz y gas")  # fmt: skip
        for week in range(4):
            amount = ars(random_.randrange(70, 120) * 1000)
            record(banco.id, expense, "Supermercado y comida", amount, on(2 + 7 * week),
                   "Supermercado")  # fmt: skip
        record(efectivo.id, expense, "Transporte", ars(random_.randrange(15, 30) * 1000), on(12),
               "SUBE")  # fmt: skip
        record(efectivo.id, expense, "Ocio", ars(random_.randrange(30, 90) * 1000), on(21),
               "Salidas")  # fmt: skip
        record(banco.id, expense, "Salud", ars(random_.randrange(20, 60) * 1000), on(15),
               "Farmacia")  # fmt: skip
        if back == 2:
            record(banco.id, expense, "Ocio", ars("1650000"), on(24), "Vacaciones")
            record(banco.id, expense, "Ropa", ars("180000"), on(26), "Ropa de verano")
        services.transactions.create_transfer(
            TransferDraft(banco.id, ahorro.id, ars(int(rate * 150)), on(20),
                          amount_in=usd(150), note="Compra de dólares MEP")
        )  # fmt: skip
        services.transactions.create_transfer(
            TransferDraft(banco.id, efectivo.id, ars("120000"), on(4), note="Extracción")
        )  # fmt: skip

    def days_ago(days: int) -> date:
        return today - timedelta(days=days)

    services.exchange_rates.set_rate(days_ago(3), Decimal("1215.50"))
    record(banco.id, income, "Sueldo", ars("1450000"), days_ago(4), "Sueldo del mes")
    record(banco.id, income, "Trabajo freelance", ars("280000"), days_ago(2), "Diseño web")
    record(banco.id, expense, "Alquiler", ars("420000"), days_ago(3), "Alquiler de noviembre")
    record(banco.id, expense, "Servicios", ars("38500.40"), days_ago(3), "Luz y gas")
    record(banco.id, expense, "Supermercado y comida", ars("96320.75"), days_ago(2),
           "Supermercado")  # fmt: skip
    record(efectivo.id, expense, "Transporte", ars("12000"), days_ago(1), "SUBE")
    record(efectivo.id, expense, "Ocio", ars("18500"), days_ago(1), "Cine")
    record(banco.id, expense, "Educación", ars("65000"), days_ago(0), "Curso de inglés")
    services.transactions.create_transfer(
        TransferDraft(banco.id, ahorro.id, ars("243100"), days_ago(1),
                      amount_in=usd("200"), note="Compra de dólares MEP")
    )  # fmt: skip

    def charge(name, account, amount, category, frequency, due):
        services.recurring.create(
            RecurringChargeDraft(name, amount, account.id, categories[(expense, category)],
                                 frequency, due)
        )  # fmt: skip

    monthly = Frequency.MONTHLY
    next_month = current.next()
    charge("Alquiler", banco, ars("420000"), "Alquiler", monthly, next_month.start.replace(day=5))
    charge("Internet", banco, ars("24900"), "Servicios", monthly, days_ago(2))
    charge("Netflix", banco, ars("8500"), "Ocio", monthly, today + timedelta(days=2))
    charge("Spotify", banco, ars("4200"), "Ocio", monthly, today + timedelta(days=9))
    charge("Gimnasio", efectivo, ars("35000"), "Salud", monthly, today + timedelta(days=12))
    charge("Seguro del auto", ahorro, usd("180"), "Transporte", Frequency.SEMIANNUAL,
           today + timedelta(days=40))  # fmt: skip
