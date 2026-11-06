"""What deserves the user's attention, gathered for the notifications panel."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from nodus.models.currency import Currency
from nodus.services.account_service import AccountService
from nodus.services.backup_service import BackupService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.recurring_charge_service import RecurringChargeService
from nodus.services.settings_service import SettingsService
from nodus.services.update_service import Release

# A rate older than this no longer reflects the dollar's price.
STALE_RATE_DAYS = 7
# Charges due within this many days are announced, besides the overdue ones.
CHARGE_NOTICE_DAYS = 3


class NoticeKind(Enum):
    UPDATE = "update"
    STALE_RATE = "stale_rate"
    BACKUP_FAILED = "backup_failed"
    CHARGES_DUE = "charges_due"


@dataclass(frozen=True)
class Notice:
    """One notification: a short title, a detail line and, for a new version, its page."""

    kind: NoticeKind
    title: str
    detail: str
    url: str = ""


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
    ) -> None:
        self._settings = settings
        self._accounts = accounts
        self._exchange_rates = exchange_rates
        self._backups = backups
        self._recurring = recurring

    def notices(self, today: date, release: Release | None) -> list[Notice]:
        notices = []
        if release is not None and release.version != self._settings.dismissed_version():
            notices.append(
                Notice(
                    NoticeKind.UPDATE,
                    f"Nodus {release.version} está disponible",
                    "Instálala encima de la actual; tus datos se conservan.",
                    release.url,
                )
            )
        rate_notice = self._rate_notice(today)
        if rate_notice:
            notices.append(rate_notice)
        charges_notice = self._charges_notice(today)
        if charges_notice:
            notices.append(charges_notice)
        if self._backups.last_error:
            notices.append(
                Notice(NoticeKind.BACKUP_FAILED, "La copia de hoy falló", self._backups.last_error)
            )
        return notices

    def dismiss(self, release: Release) -> None:
        """Stops announcing ``release``; a later version is announced again."""
        self._settings.set_dismissed_version(release.version)

    def _rate_notice(self, today: date) -> Notice | None:
        """Only matters with dollar accounts, which need the rate to be added up."""
        if not any(a.currency is Currency.USD for a in self._accounts.list_accounts()):
            return None
        rate = self._exchange_rates.rate_on(today)
        if rate is None:
            return Notice(
                NoticeKind.STALE_RATE,
                "Sin cotización del dólar",
                "Cárgala para sumar tus cuentas en pesos y en dólares.",
            )
        days = (today - rate.rate_date).days
        if days <= STALE_RATE_DAYS:
            return None
        return Notice(
            NoticeKind.STALE_RATE,
            f"Sin cotización desde hace {days} días",
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
