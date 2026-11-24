"""Names for domain values shown in the interface, in the current language."""

from datetime import date
from decimal import Decimal

from nodus.i18n import N_, _, ngettext
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.language_format import with_symbol
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.models.recurring_charge import Frequency
from nodus.models.transaction import TransactionType

ACCOUNT_TYPE_LABELS = {
    AccountType.BANK: N_("Cuenta bancaria"),
    AccountType.WALLET: N_("Billetera virtual"),
    AccountType.CASH: N_("Efectivo"),
    AccountType.CREDIT_CARD: N_("Tarjeta de crédito"),
    AccountType.SAVINGS: N_("Ahorro"),
    AccountType.INVESTMENT: N_("Inversión"),
}


def currency_label(currency: Currency) -> str:
    """ "Dólares (USD)", how a currency is offered in a list to choose from."""
    return f"{currency.name_plural.capitalize()} ({currency.value})"


def held_in_label(currency: Currency) -> str:
    """ "En dólares": where a part of the net worth is held, as the net worth card names
    it."""
    return _("En {currency}").format(currency=currency.name_plural)


# Shown where an amount cannot be converted for lack of an exchange rate.
NO_RATE_TEXT = N_("Sin cotización")
# The button that starts the guided tour, wherever it is offered.
TOUR_LABEL = N_("Ver el recorrido")

TRANSACTION_TYPE_LABELS = {
    TransactionType.EXPENSE: N_("Gasto"),
    TransactionType.INCOME: N_("Ingreso"),
}

# What each side is called when it heads a list: Categorías' sections, Beneficiarios' tabs.
KIND_TITLES = {TransactionType.EXPENSE: N_("Gastos"), TransactionType.INCOME: N_("Ingresos")}

FREQUENCY_LABELS = {
    Frequency.WEEKLY: N_("Semanal"),
    Frequency.BIWEEKLY: N_("Quincenal"),
    Frequency.MONTHLY: N_("Mensual"),
    Frequency.QUARTERLY: N_("Trimestral"),
    Frequency.SEMIANNUAL: N_("Semestral"),
    Frequency.ANNUAL: N_("Anual"),
}


def due_label(days: int) -> str:
    """When a charge is due, counted from today: "Vencido hace 3 días", "Hoy", "en 5 días"."""
    if days < -1:
        return _("Vencido hace {days} días").format(days=-days)
    if days == -1:
        return _("Vencido ayer")
    if days == 0:
        return _("Hoy")
    if days == 1:
        return _("Mañana")
    return _("en {days} días").format(days=days)


def estimate_text(amount: Money, estimate: Money | None) -> str:
    """ "≈ $ 165.000,00", what a payment of a charge in another currency is expected to
    take; empty when it is paid in its own currency or there is no estimate."""
    if estimate is None or estimate.currency is amount.currency:
        return ""
    return f"≈ {estimate.format()}"


def charge_amount_text(amount: Money, estimate: Money | None) -> str:
    """ "US$ 100,00 ≈ $ 165.000,00" for a charge paid in another currency; the plain
    amount otherwise."""
    return f"{amount.format()} {estimate_text(amount, estimate)}".rstrip()


def rate_text(base: Currency, quote: Currency, value: Decimal) -> str:
    """ "US$ 1 = $ 1.215,50", how a rate is quoted: one unit of ``base`` in ``quote``."""
    return f"{with_symbol(base.symbol, '1')} = {Money.from_decimal(value, quote).format()}"


def movements_text(count: int) -> str:
    """ "1 movimiento", "3 movimientos"."""
    return ngettext("{count} movimiento", "{count} movimientos", count).format(count=count)


def transactions_text(count: int) -> str:
    """ "1 transacción", "3 transacciones"."""
    return ngettext("{count} transacción", "{count} transacciones", count).format(count=count)


def unconverted_note(count: int) -> str:
    """Why a total may fall short: movements in another currency left out for lack of a
    rate."""
    return ngettext(
        "{count} movimiento en otra moneda sin cotización no se incluye.",
        "{count} movimientos en otra moneda sin cotización no se incluyen.",
        count,
    ).format(count=count)


# Names listed in a sentence before the rest are counted: "Vivienda, Ocio y 3 más".
LISTED_NAMES = 2


def names_text(names: list[str]) -> str:
    """ "Vivienda", "Vivienda y Ocio", or "Vivienda, Ocio y 3 más" past ``LISTED_NAMES``."""
    if len(names) <= LISTED_NAMES:
        return _(" y ").join(names)
    shown = ", ".join(names[:LISTED_NAMES])
    return _("{names} y {count} más").format(names=shown, count=len(names) - LISTED_NAMES)


def days_left_text(month: Month, today: date) -> str | None:
    """ "24 días restantes" while ``month`` is the current one; None for any other."""
    if Month.of(today) != month:
        return None
    days = month.end.day - today.day
    if days == 0:
        return _("Último día")
    return ngettext("{count} día restante", "{count} días restantes", days).format(count=days)
