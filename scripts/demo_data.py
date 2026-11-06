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
    the current month's, with one month of overspending for contrast: a trip, tagged.
    Most movements name a payee, and the supermarkets have a default category. Freelance
    work is tagged too, and two expenses are partly refunded."""
    categories = {(c.kind, c.name): c.id for c in services.categories.list_categories()}
    income, expense = TransactionType.INCOME, TransactionType.EXPENSE
    alquiler = services.categories.create(
        "Alquiler", expense, "#e67e22", parent_id=categories[(expense, "Vivienda")]
    )
    categories[(expense, "Alquiler")] = alquiler.id

    def record(account_id, kind, category, amount, day, note="", payee="", tags=(),
               refund_of=None):  # fmt: skip
        return services.transactions.create(
            TransactionDraft(account_id, kind, amount, day, categories[(kind, category)], note,
                             payee, refund_of_id=refund_of.id if refund_of else None,
                             tag_names=tuple(tags))
        )  # fmt: skip

    work = ("Trabajo",)

    for supermarket in ("Coto", "Día"):
        services.payees.create(supermarket, categories[(expense, "Supermercado y comida")])

    banco = services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("420000"))
    efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("60000"))
    ahorro = services.accounts.create("Ahorro en dólares", AccountType.SAVINGS, Currency.USD,
                                      usd("400"))  # fmt: skip

    current = Month.of(today)
    trip_month = 2  # months back
    trip = (f"Vacaciones {current.shifted(-trip_month).year}",)
    random_ = random.Random(7)
    for back in range(HISTORY_MONTHS, 0, -1):
        month = current.shifted(-back)
        rate = Decimal(1215) - Decimal(32) * back
        services.exchange_rates.set_rate(month.start, rate)

        def on(day: int, month=month) -> date:
            return date(month.year, month.month, min(day, month.end.day))

        salary = 1_300_000 + 25_000 * (HISTORY_MONTHS - back)
        record(banco.id, income, "Sueldo", ars(salary), on(3), "Sueldo del mes", "Empresa S.A.")
        if back % 2 == 0:
            record(banco.id, income, "Trabajo freelance", ars(random_.randrange(150, 320) * 1000),
                   on(18), "Proyecto freelance", tags=work)  # fmt: skip
        record(banco.id, expense, "Alquiler", ars(380_000 + 8_000 * (HISTORY_MONTHS - back)),
               on(5), "Alquiler")  # fmt: skip
        record(banco.id, expense, "Servicios", ars(random_.randrange(32, 48) * 1000), on(10),
               "Luz", "Edenor")  # fmt: skip
        for week in range(4):
            amount = ars(random_.randrange(70, 120) * 1000)
            record(banco.id, expense, "Supermercado y comida", amount, on(2 + 7 * week),
                   "Compra de la semana", "Día" if week % 2 else "Coto")  # fmt: skip
        record(efectivo.id, expense, "Transporte", ars(random_.randrange(15, 30) * 1000), on(12),
               "Carga", "SUBE")  # fmt: skip
        record(efectivo.id, expense, "Ocio", ars(random_.randrange(30, 90) * 1000), on(21),
               "Salidas")  # fmt: skip
        record(banco.id, expense, "Salud", ars(random_.randrange(20, 60) * 1000), on(15),
               "Farmacia", "Farmacity")  # fmt: skip
        if back == trip_month:
            record(banco.id, expense, "Ocio", ars("1250000"), on(24), "Pasajes y hotel",
                   tags=trip)  # fmt: skip
            record(banco.id, expense, "Ocio", ars("400000"), on(25), "Excursiones", tags=trip)
            summer_clothes = record(banco.id, expense, "Ropa", ars("180000"), on(26),
                                    "Ropa de verano", tags=trip)  # fmt: skip
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
    record(banco.id, income, "Sueldo", ars("1450000"), days_ago(4), "Sueldo del mes",
           "Empresa S.A.")  # fmt: skip
    record(banco.id, income, "Trabajo freelance", ars("280000"), days_ago(2), "Diseño web",
           tags=work)  # fmt: skip
    record(banco.id, expense, "Alquiler", ars("420000"), days_ago(3), "Alquiler de noviembre")
    record(banco.id, expense, "Servicios", ars("38500.40"), days_ago(3), "Luz", "Edenor")
    groceries = record(banco.id, expense, "Supermercado y comida", ars("96320.75"),
                       days_ago(2), "Compra de la semana", "Coto")  # fmt: skip
    record(banco.id, income, "Reembolsos", ars("9632"), days_ago(1), "Reintegro con tarjeta",
           "Coto", refund_of=groceries)  # fmt: skip
    record(banco.id, income, "Reembolsos", ars("45000"), days_ago(2), "Devolución de una campera",
           tags=trip, refund_of=summer_clothes)  # fmt: skip
    record(efectivo.id, expense, "Transporte", ars("12000"), days_ago(1), "Carga", "SUBE")
    record(efectivo.id, expense, "Ocio", ars("18500"), days_ago(1), "Cine")
    record(banco.id, expense, "Ocio", ars("52000"), days_ago(0), "Entradas recital")
    record(banco.id, expense, "Educación", ars("65000"), days_ago(0), "Curso de inglés",
           tags=work)  # fmt: skip
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

    # Budgets in every state: on track, ahead of the month, over the limit, and a limit
    # raised this month, so earlier months show the previous one.
    since = current.shifted(-(HISTORY_MONTHS - 1))
    for category, amount in (("Supermercado y comida", "350000"), ("Ocio", "60000"),
                             ("Servicios", "45000"), ("Transporte", "25000"),
                             ("Salud", "50000")):  # fmt: skip
        services.budgets.set_limit(categories[(expense, category)], since, ars(amount))
    services.budgets.set_limit(categories[(expense, "Supermercado y comida")], current,
                               ars("400000"))  # fmt: skip
