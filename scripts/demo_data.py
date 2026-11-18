"""Sample data for screenshots and manual testing. Never loaded into real user data."""

import random
from datetime import date, timedelta
from decimal import Decimal

from nodus.i18n import Language, _, current_language
from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.models.goal import GoalShare
from nodus.models.installment_plan import InstallmentPlan
from nodus.models.money import Money
from nodus.models.palette import PALETTE
from nodus.models.period import Month
from nodus.models.recurring_charge import Frequency, RecurringCharge
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.services.planning.goal_service import GoalDraft
from nodus.services.transactions.recurring_charge_service import RecurringChargeDraft
from nodus.services.transactions.transaction_service import TransactionDraft
from nodus.services.transactions.transfer_service import TransferDraft

# Months of history before the current one, so the dashboard has trends to show.
HISTORY_MONTHS = 5
INCOME, EXPENSE = TransactionType.INCOME, TransactionType.EXPENSE


# The demo's own words in English; the categories Nodus creates come from its catalog,
# so they match the names a new database gets.
ENGLISH = {
    "Banco": "Bank",
    "Efectivo": "Cash",
    "Ahorro en dólares": "Dollar savings",
    "Euros del viaje": "Travel euros",
    "Inversiones": "Investments",
    "Bancos": "Banks",
    "Billeteras": "Wallets",
    "Ahorro e inversiones": "Savings and investments",
    "Alquiler": "Rent",
    "Trabajo": "Work",
    "Empresa S.A.": "Acme Inc.",
    "Sueldo del mes": "Monthly salary",
    "Proyecto freelance": "Freelance project",
    "Luz": "Electricity",
    "Compra de la semana": "Weekly groceries",
    "Carga": "Card top-up",
    "Salidas": "Going out",
    "Farmacia": "Pharmacy",
    "Pasajes y hotel": "Flights and hotel",
    "Excursiones": "Excursions",
    "Ropa de verano": "Summer clothes",
    "Compra de dólares MEP": "MEP dollar purchase",
    "Extracción": "Cash withdrawal",
    "Diseño web": "Web design",
    "Alquiler de noviembre": "Rent for November",
    "Reintegro con tarjeta": "Card cashback",
    "Devolución de una campera": "Jacket returned",
    "Cine": "Movies",
    "Entradas recital": "Concert tickets",
    "Curso de inglés": "Language course",
    "Heladera": "Fridge",
    "Gimnasio": "Gym",
    "Seguro del auto": "Car insurance",
    "Suscripción en dólares": "Dollar subscription",
    "Vacaciones en Brasil": "Trip to Brazil",
    "Fondo de emergencia": "Emergency fund",
    "Notebook nueva": "New laptop",
    "Vacaciones {year}": "Vacation {year}",
}


def shown(text: str) -> str:
    """``text`` in the language Nodus is in, so the screenshots in English show English."""
    if current_language() is not Language.ENGLISH or not text:
        return text
    return ENGLISH.get(text) or _(text)


def ars(amount: str | int) -> Money:
    return Money.from_decimal(str(amount), Currency.ARS)


def usd(amount: str | int) -> Money:
    return Money.from_decimal(str(amount), Currency.USD)


def load_demo_data(services: Services, today: date) -> None:
    """Creates a few accounts, monthly dollar rates, five months of typical movements and
    the current month's, with one month of overspending for contrast: a trip, tagged.
    Most movements name a payee, and the supermarkets have a default category. Freelance
    work is tagged too, and two expenses are partly refunded."""
    DemoData(services, today).load()


class DemoData:
    """Fills a database with the demo, step by step; the steps run in a fixed order, so the
    same day always gives the same records and the same pictures."""

    def __init__(self, services: Services, today: date) -> None:
        self.services = services
        self.today = today
        self.current = Month.of(today)
        self.categories = {(c.kind, c.name): c.id for c in services.categories.list_categories()}
        self.work = (shown("Trabajo"),)

    def load(self) -> None:
        self.add_accounts()
        self.add_history()
        self.add_this_month()
        self.add_charges()
        self.add_installments()
        self.add_groups()
        self.add_goals()
        self.add_budgets()
        # Two colors of their own, chosen on the wheel lately, which the color picker offers.
        for color in ("#2a9d8f", "#c0587e"):
            self.services.settings.add_recent_color(color)

    def record(
        self,
        account_id: int,
        kind: TransactionType,
        category: str,
        amount: Money,
        day: date,
        note: str = "",
        payee: str = "",
        tags: tuple[str, ...] = (),
        refund_of: Transaction | None = None,
    ) -> Transaction:
        return self.services.transactions.create(
            TransactionDraft(account_id, kind, amount, day,
                             self.categories[(kind, shown(category))], shown(note),
                             shown(payee), refund_of_id=refund_of.id if refund_of else None,
                             tag_names=tuple(tags))
        )  # fmt: skip

    def days_ago(self, days: int) -> date:
        return self.today - timedelta(days=days)

    def add_accounts(self) -> None:
        """The accounts, with a category and payees of their own, and an investment that
        grows a little each month, brought up to date at each month end."""
        services = self.services
        alquiler = services.categories.create(
            shown("Alquiler"),
            EXPENSE,
            PALETTE[1],
            parent_id=self.categories[(EXPENSE, shown("Vivienda"))],
        )
        self.categories[(EXPENSE, shown("Alquiler"))] = alquiler.id
        for supermarket in ("Coto", "Día"):
            services.payees.create(
                supermarket, self.categories[(EXPENSE, shown("Supermercado y comida"))]
            )
        accounts = services.accounts
        self.banco = accounts.create(shown("Banco"), AccountType.BANK, Currency.ARS, ars("420000"))
        self.efectivo = accounts.create(
            shown("Efectivo"), AccountType.CASH, Currency.ARS, ars("60000")
        )
        self.mercado_pago = accounts.create(
            "Mercado Pago", AccountType.WALLET, Currency.ARS, ars("45000")
        )
        self.ahorro = accounts.create(
            shown("Ahorro en dólares"), AccountType.SAVINGS, Currency.USD, usd("400")
        )
        self.euros = accounts.create(
            shown("Euros del viaje"),
            AccountType.CASH,
            Currency.EUR,
            Money.from_decimal("150", Currency.EUR),
        )
        self.inversiones = accounts.create(
            shown("Inversiones"), AccountType.INVESTMENT, Currency.ARS, ars("800000")
        )
        value = 800_000
        for back in range(HISTORY_MONTHS, 0, -1):
            value = round(value * 1.025)
            accounts.adjust_value(self.inversiones.id, ars(value), self.current.shifted(-back).end)

    def add_history(self) -> None:
        """The months before this one: salary, rent, bills and shopping, a trip two months
        back, and dollars bought each month."""
        record, banco, efectivo = self.record, self.banco.id, self.efectivo.id
        trip_month = 2  # months back
        self.trip = (
            shown("Vacaciones {year}").format(year=self.current.shifted(-trip_month).year),
        )
        random_ = random.Random(7)
        for back in range(HISTORY_MONTHS, 0, -1):
            month = self.current.shifted(-back)
            rate = Decimal(1215) - Decimal(32) * back
            self.services.exchange_rates.set_rate(month.start, rate)
            self.services.exchange_rates.set_rate(month.start, rate * Decimal("1.16"), Currency.EUR)
            on = month.day
            salary = 1_300_000 + 25_000 * (HISTORY_MONTHS - back)
            record(banco, INCOME, "Sueldo", ars(salary), on(3), "Sueldo del mes", "Empresa S.A.")
            if back % 2 == 0:
                record(banco, INCOME, "Trabajo freelance", ars(random_.randrange(150, 320) * 1000),
                       on(18), "Proyecto freelance", tags=self.work)  # fmt: skip
            record(banco, EXPENSE, "Alquiler", ars(380_000 + 8_000 * (HISTORY_MONTHS - back)),
                   on(5), "Alquiler")  # fmt: skip
            record(banco, EXPENSE, "Servicios", ars(random_.randrange(32, 48) * 1000), on(10),
                   "Luz", "Edenor")  # fmt: skip
            for week in range(4):
                amount = ars(random_.randrange(70, 120) * 1000)
                record(banco, EXPENSE, "Supermercado y comida", amount, on(2 + 7 * week),
                       "Compra de la semana", "Día" if week % 2 else "Coto")  # fmt: skip
            record(efectivo, EXPENSE, "Transporte", ars(random_.randrange(15, 30) * 1000), on(12),
                   "Carga", "SUBE")  # fmt: skip
            record(efectivo, EXPENSE, "Ocio", ars(random_.randrange(30, 90) * 1000), on(21),
                   "Salidas")  # fmt: skip
            record(banco, EXPENSE, "Salud", ars(random_.randrange(20, 60) * 1000), on(15),
                   "Farmacia", "Farmacity")  # fmt: skip
            if back == trip_month:
                record(banco, EXPENSE, "Ocio", ars("1250000"), on(24), "Pasajes y hotel",
                       tags=self.trip)  # fmt: skip
                record(banco, EXPENSE, "Ocio", ars("400000"), on(25), "Excursiones", tags=self.trip)
                self.summer_clothes = record(banco, EXPENSE, "Ropa", ars("180000"), on(26),
                                             "Ropa de verano", tags=self.trip)  # fmt: skip
            self.services.transfers.create(
                TransferDraft(banco, self.ahorro.id, ars(int(rate * 150)), on(20),
                              amount_in=usd(150), note=shown("Compra de dólares MEP"))
            )  # fmt: skip
            self.services.transfers.create(
                TransferDraft(banco, efectivo, ars("120000"), on(4), note=shown("Extracción"))
            )  # fmt: skip

    def add_this_month(self) -> None:
        """The current month so far, with today's rates and two partial refunds."""
        record, days_ago = self.record, self.days_ago
        banco, efectivo = self.banco.id, self.efectivo.id
        self.services.exchange_rates.set_rate(days_ago(3), Decimal("1215.50"))
        self.services.exchange_rates.set_rate(days_ago(3), Decimal("1410.00"), Currency.EUR)
        record(banco, INCOME, "Sueldo", ars("1450000"), days_ago(4), "Sueldo del mes",
               "Empresa S.A.")  # fmt: skip
        record(banco, INCOME, "Trabajo freelance", ars("280000"), days_ago(2), "Diseño web",
               tags=self.work)  # fmt: skip
        record(banco, EXPENSE, "Alquiler", ars("420000"), days_ago(3), "Alquiler de noviembre")
        record(banco, EXPENSE, "Servicios", ars("38500.40"), days_ago(3), "Luz", "Edenor")
        groceries = record(banco, EXPENSE, "Supermercado y comida", ars("96320.75"),
                           days_ago(2), "Compra de la semana", "Coto")  # fmt: skip
        record(banco, INCOME, "Reembolsos", ars("9632"), days_ago(1), "Reintegro con tarjeta",
               "Coto", refund_of=groceries)  # fmt: skip
        record(banco, INCOME, "Reembolsos", ars("45000"), days_ago(2), "Devolución de una campera",
               tags=self.trip, refund_of=self.summer_clothes)  # fmt: skip
        record(efectivo, EXPENSE, "Transporte", ars("12000"), days_ago(1), "Carga", "SUBE")
        record(efectivo, EXPENSE, "Ocio", ars("18500"), days_ago(1), "Cine")
        record(banco, EXPENSE, "Ocio", ars("52000"), days_ago(0), "Entradas recital")
        record(banco, EXPENSE, "Educación", ars("65000"), days_ago(0), "Curso de inglés",
               tags=self.work)  # fmt: skip
        self.services.transfers.create(
            TransferDraft(banco, self.ahorro.id, ars("243100"), days_ago(1),
                          amount_in=usd("200"), note=shown("Compra de dólares MEP"))
        )  # fmt: skip

    def add_charges(self) -> None:
        """Recurring charges, due soon and later, one of them in dollars paid in pesos."""
        today, days_ago = self.today, self.days_ago

        def charge(
            name: str, account: Account, amount: Money, category: str, frequency: Frequency,
            due: date,
        ) -> RecurringCharge:  # fmt: skip
            return self.services.recurring.create(
                RecurringChargeDraft(shown(name), amount, account.id,
                                     self.categories[(EXPENSE, shown(category))], frequency,
                                     due)
            )  # fmt: skip

        monthly = Frequency.MONTHLY
        banco = self.banco
        charge("Alquiler", banco, ars("420000"), "Alquiler", monthly, self.current.next().day(5))
        charge("Internet", banco, ars("24900"), "Servicios", monthly, days_ago(2))
        charge("Netflix", banco, ars("8500"), "Ocio", monthly, today + timedelta(days=2))
        charge("Spotify", banco, ars("4200"), "Ocio", monthly, today + timedelta(days=9))
        charge(
            "Gimnasio", self.efectivo, ars("35000"), "Salud", monthly, today + timedelta(days=12)
        )
        charge("Seguro del auto", self.ahorro, usd("180"), "Transporte", Frequency.SEMIANNUAL,
               today + timedelta(days=40))  # fmt: skip
        # A subscription in dollars charged to a peso card: last month's payment, taxes
        # included, sets the estimate of the next one.
        subscription = charge("Suscripción en dólares", banco, usd("20"), "Servicios", monthly,
                              days_ago(26))  # fmt: skip
        self.services.recurring.pay(subscription.id, ars("33000"), days_ago(26), banco.id)

    def add_installments(self) -> None:
        """A fridge in six installments on a card, bought two months ago: two or three
        paid, the rest still to come off the card month by month."""
        self.visa = self.services.accounts.create(
            "Visa", AccountType.CREDIT_CARD, Currency.ARS, ars("0")
        )
        first_installment = self.current.shifted(-2).day(10)
        self.services.installments.create(
            TransactionDraft(self.visa.id, EXPENSE, ars("750000"), first_installment,
                             self.categories[(EXPENSE, shown("Vivienda"))],
                             shown("Heladera"), "Frávega"),
            InstallmentPlan(None, 6, ars("750000"), first_installment),
        )  # fmt: skip

    def add_groups(self) -> None:
        """Groups as a user would make them: the banks with their card, the wallet apart,
        and what is put aside; cash stays in no group."""
        groups = self.services.account_groups
        for name, members in ((shown("Bancos"), (self.banco, self.visa)),
                              (shown("Billeteras"), (self.mercado_pago,)),
                              (shown("Ahorro e inversiones"), (self.ahorro, self.inversiones,
                                                        self.euros))):  # fmt: skip
            group = groups.create(name)
            for account in members:
                groups.move_account(account.id, group.id)

    def add_goals(self) -> None:
        """Goals in three states: the dollar savings fill a trip on time and have already
        paid for a laptop; the investments alone fall behind an emergency fund."""
        for name, target, months, shares in (
            (shown("Vacaciones en Brasil"), usd("2000"), 14, ((self.ahorro, 70),)),
            (shown("Fondo de emergencia"), ars("1500000"), 10, ((self.inversiones, 100),)),
            (shown("Notebook nueva"), usd("300"), None, ((self.ahorro, 30),)),
        ):
            target_date = self.current.shifted(months).end if months else None
            self.services.goals.create(
                GoalDraft(name, target, target_date, tuple(GoalShare(a.id, p) for a, p in shares)),
                self.today,
            )
        self.services.goals.check_reached(self.today)

    def add_budgets(self) -> None:
        """Budgets in every state: on track, ahead of the month, over the limit, and a limit
        raised this month, so earlier months show the previous one."""
        budgets, categories = self.services.budgets, self.categories
        since = self.current.shifted(-(HISTORY_MONTHS - 1))
        for category, amount in (("Supermercado y comida", "350000"), ("Ocio", "60000"),
                                 ("Servicios", "45000"), ("Transporte", "25000"),
                                 ("Salud", "50000")):  # fmt: skip
            budgets.set_limit(categories[(EXPENSE, shown(category))], since, ars(amount))
        budgets.set_limit(categories[(EXPENSE, shown("Supermercado y comida"))], self.current,
                          ars("400000"))  # fmt: skip
