"""What deserves the user's attention, gathered for the notifications panel."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import Enum

from nodus.models.currency import Currency
from nodus.services.accounts.account_service import AccountService
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.app.seen_service import SeenService
from nodus.services.app.settings_service import SettingsService
from nodus.services.backup_service import BackupService, reminder_start
from nodus.services.external.update_service import Release
from nodus.services.planning.budget_service import BudgetService
from nodus.services.planning.goal_service import GoalService
from nodus.services.transactions.recurring_charge_service import RecurringChargeService

# A rate older than this no longer reflects the currency's price.
STALE_RATE_DAYS = 7
# Charges due within this many days are announced, besides the overdue ones.
CHARGE_NOTICE_DAYS = 3
# How the record of what the user saw names a version found.
UPDATE_PREFIX = "update:"


# The keys of the record of what the user saw, one per kind of thing announced. They are
# stored, so changing one makes every notice of its kind look new again. A charge names
# its own (``RecurringCharge.seen_key``).
def _update_key(version: str) -> str:
    return f"{UPDATE_PREFIX}{version}"


def _backup_failed_key(today: date) -> str:
    return f"backup-failed:{today}"


def _backup_reminder_key(month_start: date) -> str:
    return f"backup:{month_start:%Y-%m}"


def _goal_key(goal_id: int) -> str:
    return f"goal:{goal_id}"


def _rate_key(currency: Currency, rate_date: date | None) -> str:
    return f"rate:{currency.value}:{rate_date or 'none'}"


def _budget_key(today: date, category_id: int) -> str:
    return f"budget:{today:%Y-%m}:{category_id}"


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
    GOAL_REACHED = "goal_reached"


@dataclass(frozen=True)
class Notice:
    """One notification: a short title, a detail line and, for a new version, its page
    and release notes; ``item_id`` names what it is about, such as a goal.

    ``items`` are the keys of what it is about, in the record of what the user saw
    (``SeenService``): one per charge or budget of a notice that gathers several. They
    say what it is about, not how it reads, so they stay the same while the texts change
    by the day («vence mañana», the amount over a budget). ``seen`` says whether the user
    already saw every one of them: paying one of two charges leaves the other as seen
    as it was, and another budget passing makes the notice new again."""

    kind: NoticeKind
    title: str
    detail: str
    url: str = ""
    notes: str = ""
    item_id: int | None = None
    items: tuple[str, ...] = ()
    seen: bool = False


class NotificationService:
    """Builds the list of notices from the app's state and the latest release found.
    What the user saw lives in ``SeenService``, shared with «Ya lo vi» on charges; this
    service only adds which new version to ignore."""

    def __init__(
        self,
        settings: SettingsService,
        seen: SeenService,
        accounts: AccountService,
        exchange_rates: ExchangeRateService,
        backups: BackupService,
        recurring: RecurringChargeService,
        budgets: BudgetService,
        goals: GoalService,
    ) -> None:
        self._settings = settings
        self._seen = seen
        self._release: Release | None = None
        self._accounts = accounts
        self._exchange_rates = exchange_rates
        self._backups = backups
        self._recurring = recurring
        self._budgets = budgets
        self._goals = goals

    @property
    def release(self) -> Release | None:
        """The newer version found, if any; None until the check answers."""
        return self._release

    def set_release(self, release: Release | None) -> None:
        self._release = release

    def notices(self, today: date) -> list[Notice]:
        """Every notice, the ones not seen yet first."""
        current = self._current(today)
        self._forget_what_no_longer_applies(today, current)
        seen = self._seen.all()
        notices = [replace(n, seen=set(n.items) <= seen) for n in current]
        return sorted(notices, key=lambda notice: notice.seen)

    def mark_seen(self, notice: Notice) -> None:
        """Remembers that the user saw everything ``notice`` is about."""
        self._seen.mark(notice.items)

    def _forget_what_no_longer_applies(self, today: date, current: list[Notice]) -> None:
        """Keeps the record as short as the day's notices. A charge seen with «Ya lo vi»
        is kept even before it enters the bell, and a version seen is kept while the
        check has not answered yet."""
        keep = {item for notice in current for item in notice.items}
        keep |= {c.seen_key(today) for c in self._recurring.list_charges() if c.is_active}
        if self._release is None:
            keep |= {key for key in self._seen.all() if key.startswith(UPDATE_PREFIX)}
        self._seen.keep_only(keep)

    def _current(self, today: date) -> list[Notice]:
        notices = []
        release = self._release
        if release is not None and release.version != self._settings.dismissed_version():
            notices.append(
                Notice(
                    NoticeKind.UPDATE,
                    f"Nodus {release.version} está disponible",
                    "Se instala en un momento y tus datos se conservan.",
                    release.url,
                    release.notes,
                    items=(_update_key(release.version),),
                )
            )
        notices.extend(self._goal_notices(today))
        notices.extend(self._rate_notices(today))
        for notice in (self._charges_notice(today), self._budgets_notice(today)):
            if notice:
                notices.append(notice)
        if self._backups.last_error:
            notices.append(
                Notice(
                    NoticeKind.BACKUP_FAILED,
                    "La copia de hoy falló",
                    self._backups.last_error,
                    items=(_backup_failed_key(today),),
                )
            )
        reminder = self._backup_reminder(today)
        if reminder:
            notices.append(reminder)
        return notices

    def _goal_notices(self, today: date) -> list[Notice]:
        """Each goal reached, once: until the user opens it or puts the notice away.
        Reaching is checked here, as the bell refreshes whenever balances may change."""
        self._goals.check_reached(today)
        return [
            Notice(
                NoticeKind.GOAL_REACHED,
                f"Alcanzaste «{goal.name}»",
                "Archívala para usar sus cuentas en otra meta, o súbele el objetivo.",
                item_id=goal.id,
                items=(_goal_key(goal.id),),
            )
            for goal in self._goals.unseen_reached()
        ]

    def dismiss_release(self) -> None:
        """Stops announcing the version found; a later one is announced again."""
        if self._release is not None:
            self._settings.set_dismissed_version(self._release.version)

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
            items=(_backup_reminder_key(reminder_start(today)),),
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
                items=(_rate_key(currency, None),),
            )
        days = (today - rate.rate_date).days
        if days <= STALE_RATE_DAYS:
            return None
        return Notice(
            NoticeKind.STALE_RATE,
            f"Sin cotización del {name} desde hace {days} días",
            f"La última es del {rate.rate_date:%d/%m/%Y}.",
            items=(_rate_key(currency, rate.rate_date),),
        )

    def _charges_notice(self, today: date) -> Notice | None:
        """Overdue charges and those due in the next days, in a single notice. A charge
        seen here or with «Ya lo vi» stays seen until the day before it is due."""
        charges = self._recurring.upcoming(today, CHARGE_NOTICE_DAYS)
        if not charges:
            return None
        overdue = sum(1 for c in charges if c.days_until(today) < 0)
        items = tuple(c.seen_key(today) for c in charges)
        if len(charges) == 1:
            charge = charges[0]
            return Notice(
                NoticeKind.CHARGES_DUE,
                f"{charge.name} {_due_phrase(charge.days_until(today))}",
                f"{charge.amount.format()} · Regístralo desde Recurrentes.",
                items=items,
            )
        title = f"{len(charges)} cargos por pagar"
        if overdue:
            title += f" ({overdue} vencido{'s' if overdue > 1 else ''})"
        names = ", ".join(c.name for c in charges) + "."
        return Notice(NoticeKind.CHARGES_DUE, title, names, items=items)

    def _budgets_notice(self, today: date) -> Notice | None:
        """The budgets already passed this month, in a single notice. Spending more on
        one already passed is not news; another one passing, or a new month, is."""
        over = self._budgets.over_limit(today)
        if not over:
            return None
        items = tuple(_budget_key(today, b.category.id) for b in over)
        if len(over) == 1:
            budget = over[0]
            return Notice(
                NoticeKind.BUDGET_OVER,
                f"{budget.category.name} pasó su límite",
                f"Excedido en {(-budget.remaining).format()} este mes.",
                items=items,
            )
        return Notice(
            NoticeKind.BUDGET_OVER,
            f"{len(over)} presupuestos excedidos",
            ", ".join(b.category.name for b in over) + ".",
            items=items,
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
