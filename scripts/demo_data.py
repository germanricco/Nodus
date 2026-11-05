"""Sample data for screenshots and manual testing. Never loaded into real user data."""

from datetime import date, timedelta
from decimal import Decimal

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.services.transaction_service import TransactionDraft, TransferDraft


def load_demo_data(services: Services, today: date) -> None:
    """Creates a few accounts, a dollar rate and a month of typical transactions."""

    def ars(amount: str) -> Money:
        return Money.from_decimal(amount, Currency.ARS)

    def usd(amount: str) -> Money:
        return Money.from_decimal(amount, Currency.USD)

    categories = {(c.kind, c.name): c.id for c in services.categories.list_categories()}

    def record(account_id, kind, category, amount, days_ago, note=""):
        services.transactions.create(
            TransactionDraft(
                account_id, kind, amount, today - timedelta(days=days_ago),
                categories[(kind, category)], note,
            )
        )  # fmt: skip

    banco = services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("350000"))
    efectivo = services.accounts.create("Efectivo", AccountType.CASH, Currency.ARS, ars("50000"))
    ahorro = services.accounts.create("Ahorro en dólares", AccountType.SAVINGS, Currency.USD,
                                      usd("1200"))  # fmt: skip
    services.exchange_rates.set_rate(today - timedelta(days=3), Decimal("1215.50"))

    income, expense = TransactionType.INCOME, TransactionType.EXPENSE
    alquiler = services.categories.create(
        "Alquiler", expense, "#e67e22", parent_id=categories[(expense, "Vivienda")]
    )
    categories[(expense, "Alquiler")] = alquiler.id
    record(banco.id, income, "Sueldo", ars("1450000"), 4, "Sueldo del mes")
    record(banco.id, income, "Trabajo freelance", ars("280000"), 2, "Diseño web")
    record(banco.id, expense, "Alquiler", ars("420000"), 3, "Alquiler de noviembre")
    record(banco.id, expense, "Servicios", ars("38500.40"), 3, "Luz y gas")
    record(banco.id, expense, "Supermercado y comida", ars("96320.75"), 2, "Supermercado")
    record(efectivo.id, expense, "Transporte", ars("12000"), 1, "SUBE")
    record(efectivo.id, expense, "Ocio", ars("18500"), 1, "Cine")
    record(banco.id, expense, "Educación", ars("65000"), 0, "Curso de inglés")
    services.transactions.create_transfer(
        TransferDraft(banco.id, ahorro.id, ars("243100"), today - timedelta(days=1),
                      amount_in=usd("200"), note="Compra de dólares MEP")
    )  # fmt: skip
