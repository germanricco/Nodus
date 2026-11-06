"""Spanish names for domain values shown in the interface."""

from datetime import date

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.period import Month
from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import TransactionType

ACCOUNT_TYPE_LABELS = {
    AccountType.BANK: "Cuenta bancaria",
    AccountType.CASH: "Efectivo",
    AccountType.CREDIT_CARD: "Tarjeta de crédito",
    AccountType.SAVINGS: "Ahorro",
    AccountType.INVESTMENT: "Inversión",
}

CURRENCY_LABELS = {
    Currency.ARS: "Pesos (ARS)",
    Currency.USD: "Dólares (USD)",
}

TRANSACTION_TYPE_LABELS = {
    TransactionType.EXPENSE: "Gasto",
    TransactionType.INCOME: "Ingreso",
}

FREQUENCY_LABELS = {
    Frequency.WEEKLY: "Semanal",
    Frequency.BIWEEKLY: "Quincenal",
    Frequency.MONTHLY: "Mensual",
    Frequency.QUARTERLY: "Trimestral",
    Frequency.SEMIANNUAL: "Semestral",
    Frequency.ANNUAL: "Anual",
}


def due_label(days: int) -> str:
    """When a charge is due, counted from today: "Vencido hace 3 días", "Hoy", "en 5 días"."""
    if days < -1:
        return f"Vencido hace {-days} días"
    if days == -1:
        return "Vencido ayer"
    if days == 0:
        return "Hoy"
    if days == 1:
        return "Mañana"
    return f"en {days} días"


def unconverted_note(count: int) -> str:
    """Why a total may fall short: dollar movements left out for lack of a rate."""
    return f"{count} movimiento(s) en dólares sin cotización no se incluyen."


def days_left_text(month: Month, today: date) -> str | None:
    """ "24 días restantes" while ``month`` is the current one; None for any other."""
    if Month.of(today) != month:
        return None
    days = month.end.day - today.day
    if days == 0:
        return "Último día"
    return "1 día restante" if days == 1 else f"{days} días restantes"
