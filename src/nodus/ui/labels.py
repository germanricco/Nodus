"""Spanish names for domain values shown in the interface."""

from nodus.models.account import AccountType
from nodus.models.currency import Currency

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
