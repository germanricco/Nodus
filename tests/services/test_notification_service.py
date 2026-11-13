from datetime import date, timedelta
from decimal import Decimal

import pytest
from factories import TODAY, ars, category_id, charge_draft, data_since, eur, expense_draft

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.services.notification_service import STALE_RATE_DAYS, NoticeKind
from nodus.services.update_service import Release

RELEASE = Release("9.0.0", "https://example.com/v9")


def kinds(services, release=None):
    return [n.kind for n in services.notifications.notices(TODAY, release)]


def test_nothing_to_say(services, pesos):
    assert kinds(services) == []


def test_new_release_until_dismissed(services):
    assert kinds(services, RELEASE) == [NoticeKind.UPDATE]

    services.notifications.dismiss(RELEASE)

    assert kinds(services, RELEASE) == []
    assert kinds(services, Release("9.1.0", "")) == [NoticeKind.UPDATE]


def test_rate_matters_only_with_dollar_accounts(services, pesos):
    assert kinds(services) == []


def test_missing_rate_with_dollar_accounts(services, dollars):
    notices = services.notifications.notices(TODAY, None)

    assert [n.kind for n in notices] == [NoticeKind.STALE_RATE]
    assert notices[0].title == "Sin cotización del dólar"


def test_rate_becomes_stale_after_a_week(services, dollars):
    services.exchange_rates.set_rate(TODAY - timedelta(days=STALE_RATE_DAYS), Decimal("1000"))
    assert kinds(services) == []

    services.exchange_rates.set_rate(TODAY - timedelta(days=STALE_RATE_DAYS + 3), Decimal("1"))
    services.exchange_rates.delete(services.exchange_rates.history()[0].id)

    notices = services.notifications.notices(TODAY, None)
    assert notices[0].title == f"Sin cotización del dólar desde hace {STALE_RATE_DAYS + 3} días"


def test_failed_backup(services):
    services.backups.last_error = "No se pudo hacer la copia del día: disco lleno"

    notices = services.notifications.notices(TODAY, None)

    assert [n.kind for n in notices] == [NoticeKind.BACKUP_FAILED]
    assert "disco lleno" in notices[0].detail


def charges_notice(services):
    return next(
        (
            n
            for n in services.notifications.notices(TODAY, None)
            if n.kind is NoticeKind.CHARGES_DUE
        ),
        None,
    )


def test_one_charge_due_soon(services, pesos):
    services.recurring.create(
        charge_draft(services, pesos.id, ars("8500"), TODAY + timedelta(days=1), name="Netflix")
    )

    notice = charges_notice(services)

    assert notice.title == "Netflix vence mañana"
    assert notice.detail.startswith("$ 8.500,00")


def test_several_charges_with_overdue_ones(services, pesos):
    for name, days in (("Internet", -2), ("Netflix", 0), ("Spotify", 3), ("Gimnasio", 4)):
        services.recurring.create(
            charge_draft(services, pesos.id, ars("1"), TODAY + timedelta(days=days), name=name)
        )

    notice = charges_notice(services)

    assert notice.title == "3 cargos por pagar (1 vencido)"
    assert notice.detail == "Internet, Netflix, Spotify."


def test_no_charges_notice_for_paused_or_distant_charges(services, pesos):
    later = services.recurring.create(
        charge_draft(services, pesos.id, ars("1"), TODAY + timedelta(days=10))
    )
    paused = services.recurring.create(charge_draft(services, pesos.id, ars("1"), TODAY))
    services.recurring.set_active(paused.id, False)

    assert charges_notice(services) is None
    assert later.id


def budget(services, name, limit):
    category = category_id(services, name, TransactionType.EXPENSE)
    services.budgets.set_limit(category, Month.of(TODAY), ars(limit))
    return category


def test_a_budget_passed_this_month(services, pesos):
    food = budget(services, "Supermercado y comida", "1000")
    services.transactions.create(expense_draft(services, pesos.id, ars("1000")))
    assert kinds(services) == []  # right at the limit is fine

    services.transactions.create(expense_draft(services, pesos.id, ars("250"), category_id=food))

    (notice,) = services.notifications.notices(TODAY, None)
    assert notice.kind is NoticeKind.BUDGET_OVER
    assert notice.title == "Supermercado y comida pasó su límite"
    assert notice.detail == "Excedido en $ 250,00 este mes."


def test_several_budgets_passed_in_one_notice(services, pesos):
    for name in ("Ocio", "Ropa"):
        category = budget(services, name, "10")
        services.transactions.create(
            expense_draft(services, pesos.id, ars("20"), category_id=category)
        )

    (notice,) = services.notifications.notices(TODAY, None)
    assert notice.title == "2 presupuestos excedidos"
    assert notice.detail == "Ocio, Ropa."


def test_each_foreign_currency_held_needs_its_rate(services, dollars):
    services.accounts.create("Europa", AccountType.CASH, Currency.EUR, eur("100"))
    services.exchange_rates.set_rate(TODAY, Decimal("1000"))

    [notice] = services.notifications.notices(TODAY, None)

    assert notice.title == "Sin cotización del euro"
    assert notice.detail == "Cárgala para sumar tus cuentas en euros al resto."


class TestBackupReminder:
    """Once a month, to save a copy outside the computer (November has 30 days)."""

    @pytest.fixture(autouse=True)
    def old_data(self, database, pesos):
        data_since(database, date(2026, 1, 10))

    @staticmethod
    def reminded(services, day) -> bool:
        return NoticeKind.BACKUP_REMINDER in [
            n.kind for n in services.notifications.notices(day, None)
        ]

    def test_from_the_28th_without_a_copy_this_month(self, services, tmp_path):
        services.backups.export_to(tmp_path, date(2026, 10, 10))

        assert not self.reminded(services, date(2026, 11, 27))
        assert self.reminded(services, date(2026, 11, 28))

    def test_not_with_a_copy_this_month(self, services, tmp_path):
        services.backups.export_to(tmp_path, date(2026, 11, 2))

        assert not self.reminded(services, date(2026, 11, 29))

    def test_goes_on_into_the_next_month_until_there_is_one(self, services, tmp_path):
        assert self.reminded(services, date(2026, 12, 3))

        services.backups.export_to(tmp_path, date(2026, 12, 3))

        assert not self.reminded(services, date(2026, 12, 4))

    def test_put_off_until_the_next_months_end(self, services):
        services.backups.put_off_reminder(date(2026, 11, 29))

        assert not self.reminded(services, date(2026, 12, 3))
        assert self.reminded(services, date(2026, 12, 29))

    def test_turned_off(self, services):
        services.settings.set_backup_reminder(False)

        assert not self.reminded(services, date(2026, 11, 29))

    def test_new_data_waits_for_its_first_months_end(self, services, database):
        data_since(database, date(2026, 11, 29))

        assert not self.reminded(services, date(2026, 11, 30))
        assert self.reminded(services, date(2026, 12, 29))

    def test_says_when_the_last_copy_was(self, services, tmp_path):
        notice = services.notifications.notices(date(2026, 11, 28), None)[-1]
        assert notice.title == "Guarda una copia fuera de esta computadora"
        assert notice.detail.startswith("Todavía no guardaste ninguna.")

        services.backups.export_to(tmp_path, date(2026, 10, 10))

        notice = services.notifications.notices(date(2026, 11, 28), None)[-1]
        assert notice.detail.startswith("La última es del 10/10/2026.")
