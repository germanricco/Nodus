"""What deserves the user's attention, gathered for the notifications panel."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.models.currency import Currency
from nodus.services.account_service import AccountService
from nodus.services.backup_service import BackupService
from nodus.services.budget_service import BudgetService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.recurring_charge_service import RecurringChargeService
from nodus.services.settings_service import SettingsService
from nodus.services.update_service import Release

# A rate older than this no longer reflects the currency's price.
STALE_RATE_DAYS = 7
# Charges due within this many days are announced, besides the overdue ones.
CHARGE_NOTICE_DAYS = 3


# How the notices name each foreign currency: singular and plural.
_CURRENCY_NAMES = {
    Currency.USD: ("dólar", "dólares"),
    Currency.EUR: ("euro", "euros"),
    Currency.CLP: ("peso chileno", "pesos chilenos"),
}


class NoticeKind(Enum):
    UPDATE = "update"
    STALE_RATE = "stale_rate"
    BACKUP_FAILED = "backup_failed"
    BACKUP_REMINDER = "backup_reminder"
    CHARGES_DUE = "charges_due"
    BUDGET_OVER = "budget_over"


@dataclass(frozen=True)
class Notice:
    """One notification: a short title, a detail line and, for a new version, its page
    and release notes."""

    kind: NoticeKind
    title: str
    detail: str
    url: str = ""
    notes: str = ""


class NotificationService:
    """Builds the list of notices from the app's state; it stores nothing but which new
    version the user chose to ignore."""

    def __init__(
        self,
        settings: SettingsService,
        accounts: AccountService,
        exchange_rates: ExchangeRateService,
        backups: BackupService,
        recurring: RecurringChargeService,
        budgets: BudgetService,
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._exchange_rates = exchange_rates
        self._backups = backups
        self._recurring = recurring
        self._budgets = budgets

    def notices(self, today: date, release: Release | None) -> list[Notice]:
        notices = []
        if release is not None and release.version != self._settings.dismissed_version():
            notices.append(
                Notice(
                    NoticeKind.UPDATE,
                    f"Nodus {release.version} está disponible",
                    "Se instala en un momento y tus datos se conservan.",
                    release.url,
                    release.notes,
                )
            )
        notices.extend(self._rate_notices(today))
        for notice in (self._charges_notice(today), self._budgets_notice(today)):
            if notice:
                notices.append(notice)
        if self._backups.last_error:
            notices.append(
                Notice(NoticeKind.BACKUP_FAILED, "La copia de hoy falló", self._backups.last_error)
            )
        reminder = self._backup_reminder(today)
        if reminder:
            notices.append(reminder)
        return notices

    def dismiss(self, release: Release) -> None:
        """Stops announcing ``release``; a later version is announced again."""
        self._settings.set_dismissed_version(release.version)

    def _backup_reminder(self, today: date) -> Notice | None:
        """At the end of the month, to save a copy outside the computer."""
        if not self._backups.reminder_due(today, self._accounts.first_created_on()):
            return None
        last = self._backups.last_external_backup()
        since = f"La última es del {last:%d/%m/%Y}." if last else "Todavía no guardaste ninguna."
        return Notice(
            NoticeKind.BACKUP_REMINDER,
            "Guarda una copia fuera de esta computadora",
            f"{since} En un pendrive o en Drive, tus datos se salvan aunque la PC se pierda"
            " o se rompa.",
        )

    def _rate_notices(self, today: date) -> list[Notice]:
        """One per foreign currency an account holds, since its rate is needed to add it
        up; currencies nobody holds do not matter."""
        held = {account.currency for account in self._accounts.list_accounts()}
        notices = (self._rate_notice(c, today) for c in Currency if c.is_foreign and c in held)
        return [notice for notice in notices if notice]

    def _rate_notice(self, currency: Currency, today: date) -> Notice | None:
        name, plural = _CURRENCY_NAMES[currency]
        rate = self._exchange_rates.rate_on(today, currency)
        if rate is None:
            return Notice(
                NoticeKind.STALE_RATE,
                f"Sin cotización del {name}",
                f"Cárgala para sumar tus cuentas en {plural} al resto.",
            )
        days = (today - rate.rate_date).days
        if days <= STALE_RATE_DAYS:
            return None
        return Notice(
            NoticeKind.STALE_RATE,
            f"Sin cotización del {name} desde hace {days} días",
            f"La última es del {rate.rate_date:%d/%m/%Y}.",
        )

    def _charges_notice(self, today: date) -> Notice | None:
        """Overdue charges and those due in the next days, in a single notice."""
        charges = self._recurring.upcoming(today, CHARGE_NOTICE_DAYS)
        if not charges:
            return None
        if len(charges) == 1:
            charge = charges[0]
            return Notice(
                NoticeKind.CHARGES_DUE,
                f"{charge.name} {_due_phrase(charge.days_until(today))}",
                f"{charge.amount.format()} · Regístralo desde Cargos recurrentes.",
            )
        overdue = sum(1 for c in charges if c.days_until(today) < 0)
        title = f"{len(charges)} cargos por pagar"
        if overdue:
            title += f" ({overdue} vencido{'s' if overdue > 1 else ''})"
        return Notice(NoticeKind.CHARGES_DUE, title, ", ".join(c.name for c in charges) + ".")

    def _budgets_notice(self, today: date) -> Notice | None:
        """The budgets already passed this month, in a single notice."""
        over = self._budgets.over_limit(today)
        if not over:
            return None
        if len(over) == 1:
            budget = over[0]
            return Notice(
                NoticeKind.BUDGET_OVER,
                f"{budget.category.name} pasó su límite",
                f"Excedido en {(-budget.remaining).format()} este mes.",
            )
        return Notice(
            NoticeKind.BUDGET_OVER,
            f"{len(over)} presupuestos excedidos",
            ", ".join(b.category.name for b in over) + ".",
        )


def _due_phrase(days: int) -> str:
    """ "vence mañana", "venció hace 2 días"…"""
    if days < -1:
        return f"venció hace {-days} días"
    if days == -1:
        return "venció ayer"
    if days == 0:
        return "vence hoy"
    if days == 1:
        return "vence mañana"
    return f"vence en {days} días"
