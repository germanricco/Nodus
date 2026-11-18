from datetime import date, timedelta
from decimal import Decimal

import pytest
from factories import TODAY, ars, category_id, charge_draft, data_since, eur, expense_draft

from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.models.period import Month
from nodus.models.transaction import TransactionType
from nodus.services.app.notification_service import STALE_RATE_DAYS, NoticeKind
from nodus.services.external.update_service import Release

RELEASE = Release("9.0.0", "https://example.com/v9")


def kinds(services, release=None):
    services.notifications.set_release(release)
    return [n.kind for n in services.notifications.notices(TODAY)]


def test_nothing_to_say(services, pesos):
    assert kinds(services) == []


def test_new_release_until_dismissed(services):
    assert kinds(services, RELEASE) == [NoticeKind.UPDATE]

    services.notifications.dismiss_release()

    assert kinds(services, RELEASE) == []
    assert kinds(services, Release("9.1.0", "")) == [NoticeKind.UPDATE]


def test_rate_matters_only_with_dollar_accounts(services, pesos):
    assert kinds(services) == []


def test_missing_rate_with_dollar_accounts(services, dollars):
    notices = services.notifications.notices(TODAY)

    assert [n.kind for n in notices] == [NoticeKind.STALE_RATE]
    assert notices[0].title == "Sin cotización del dólar"


def test_rate_becomes_stale_after_a_week(services, dollars):
    services.exchange_rates.set_rate(TODAY - timedelta(days=STALE_RATE_DAYS), Decimal("1000"))
    assert kinds(services) == []

    services.exchange_rates.set_rate(TODAY - timedelta(days=STALE_RATE_DAYS + 3), Decimal("1"))
    services.exchange_rates.delete(services.exchange_rates.history()[0].id)

    notices = services.notifications.notices(TODAY)
    assert notices[0].title == f"Sin cotización del dólar desde hace {STALE_RATE_DAYS + 3} días"


def test_failed_backup(services):
    services.backups.last_error = "No se pudo hacer la copia del día: disco lleno"

    notices = services.notifications.notices(TODAY)

    assert [n.kind for n in notices] == [NoticeKind.BACKUP_FAILED]
    assert "disco lleno" in notices[0].detail


def charges_notice(services):
    return next(
        (n for n in services.notifications.notices(TODAY) if n.kind is NoticeKind.CHARGES_DUE),
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


def test_in_english_the_charges_notice_counts_in_english(english, services, pesos):
    for name, days in (("Internet", -2), ("Netflix", 0), ("Spotify", 3)):
        services.recurring.create(
            charge_draft(services, pesos.id, ars("1"), TODAY + timedelta(days=days), name=name)
        )

    assert charges_notice(services).title == "3 charges to pay (1 overdue)"


@pytest.mark.parametrize(
    ("days", "title"),
    [
        (-2, "Netflix was due 2 days ago"),
        (0, "Netflix is due today"),
        (2, "Netflix is due in 2 days"),
    ],
)
def test_in_english_one_charge_says_when_it_is_due(english, services, pesos, days, title):
    services.recurring.create(
        charge_draft(services, pesos.id, ars("8500"), TODAY + timedelta(days=days), name="Netflix")
    )

    notice = charges_notice(services)

    assert notice.title == title
    assert notice.detail == "$8,500.00 · Record it from Recurring."


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

    (notice,) = services.notifications.notices(TODAY)
    assert notice.kind is NoticeKind.BUDGET_OVER
    assert notice.title == "Supermercado y comida pasó su límite"
    assert notice.detail == "Excedido en $ 250,00 este mes."


def test_several_budgets_passed_in_one_notice(services, pesos):
    for name in ("Ocio", "Ropa"):
        category = budget(services, name, "10")
        services.transactions.create(
            expense_draft(services, pesos.id, ars("20"), category_id=category)
        )

    (notice,) = services.notifications.notices(TODAY)
    assert notice.title == "2 presupuestos excedidos"
    assert notice.detail == "Ocio, Ropa."


def test_each_foreign_currency_held_needs_its_rate(services, dollars):
    services.accounts.create("Europa", AccountType.CASH, Currency.EUR, eur("100"))
    services.exchange_rates.set_rate(TODAY, Decimal("1000"))

    [notice] = services.notifications.notices(TODAY)

    assert notice.title == "Sin cotización del euro"
    assert notice.detail == "Cárgala para sumar tus cuentas en euros al resto."


class TestBackupReminder:
    """Once a month, to save a copy outside the computer (November has 30 days)."""

    @pytest.fixture(autouse=True)
    def old_data(self, database, pesos):
        data_since(database, date(2026, 1, 10))

    @staticmethod
    def reminded(services, day) -> bool:
        return NoticeKind.BACKUP_REMINDER in [n.kind for n in services.notifications.notices(day)]

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
        notice = services.notifications.notices(date(2026, 11, 28))[-1]
        assert notice.title == "Guarda una copia fuera de esta computadora"
        assert notice.detail.startswith("Todavía no guardaste ninguna.")

        services.backups.export_to(tmp_path, date(2026, 10, 10))

        notice = services.notifications.notices(date(2026, 11, 28))[-1]
        assert notice.detail.startswith("La última es del 10/10/2026.")


def test_a_charge_seen_with_ya_lo_vi_is_seen_in_the_bell(services, pesos):
    charge = services.recurring.create(
        charge_draft(services, pesos.id, ars("1"), TODAY + timedelta(days=3), name="Netflix")
    )

    services.recurring.mark_seen(charge.id, TODAY)

    assert charges_notice(services).seen


class TestSeen:
    """Opening a notice marks it seen until there is something new about it."""

    @staticmethod
    def open(services, notice, day=TODAY):
        services.notifications.mark_seen(notice)

    @staticmethod
    def seen(services, day=TODAY):
        return [n.seen for n in services.notifications.notices(day)]

    @staticmethod
    def spend(services, pesos, category, amount):
        services.transactions.create(
            expense_draft(services, pesos.id, ars(amount), category_id=category)
        )

    def test_an_opened_notice_stays_listed_after_the_new_ones(self, services, pesos, dollars):
        self.spend(services, pesos, budget(services, "Ocio", "10"), "20")
        notices = services.notifications.notices(TODAY)
        [over] = [n for n in notices if n.kind is NoticeKind.BUDGET_OVER]

        self.open(services, over)

        notices = services.notifications.notices(TODAY)
        assert [(n.kind, n.seen) for n in notices] == [
            (NoticeKind.STALE_RATE, False),
            (NoticeKind.BUDGET_OVER, True),
        ]

    def test_spending_more_on_a_passed_budget_is_not_news(self, services, pesos):
        leisure = budget(services, "Ocio", "10")
        self.spend(services, pesos, leisure, "20")
        self.open(services, services.notifications.notices(TODAY)[0])

        self.spend(services, pesos, leisure, "50")

        assert self.seen(services) == [True]

    def test_another_budget_passing_is(self, services, pesos):
        self.spend(services, pesos, budget(services, "Ocio", "10"), "20")
        self.open(services, services.notifications.notices(TODAY)[0])

        self.spend(services, pesos, budget(services, "Ropa", "10"), "20")

        assert self.seen(services) == [False]

    def test_a_charge_is_new_again_the_day_before_and_once_overdue(self, services, pesos):
        services.recurring.create(
            charge_draft(services, pesos.id, ars("1"), TODAY + timedelta(days=3))
        )
        self.open(services, charges_notice(services))
        assert self.seen(services, TODAY + timedelta(days=1)) == [True]

        assert self.seen(services, TODAY + timedelta(days=2)) == [False]  # the day before
        self.open(services, services.notifications.notices(TODAY + timedelta(days=2))[0])
        assert self.seen(services, TODAY + timedelta(days=4)) == [False]  # overdue

    def test_seeing_charges_in_the_bell_is_ya_lo_vi_on_them(self, services, pesos):
        charge = services.recurring.create(
            charge_draft(services, pesos.id, ars("1"), TODAY + timedelta(days=3))
        )

        self.open(services, charges_notice(services))

        assert services.recurring.is_quiet(services.recurring.get(charge.id), TODAY)

    def test_ya_lo_vi_on_one_charge_leaves_the_others_seen(self, services, pesos):
        for name, days in (("Internet", -1), ("Netflix", 3)):
            services.recurring.create(
                charge_draft(services, pesos.id, ars("1"), TODAY + timedelta(days=days), name=name)
            )
        self.open(services, charges_notice(services))
        netflix = next(c for c in services.recurring.list_charges() if c.name == "Netflix")

        services.recurring.remind_again(netflix.id, TODAY)
        services.recurring.mark_seen(netflix.id, TODAY)

        assert charges_notice(services).seen

    def test_paying_one_charge_leaves_the_others_seen(self, services, pesos):
        for name in ("Internet", "Luz"):
            services.recurring.create(
                charge_draft(services, pesos.id, ars("1"), TODAY - timedelta(days=1), name=name)
            )
        self.open(services, charges_notice(services))
        internet = next(c for c in services.recurring.list_charges() if c.name == "Internet")

        services.recurring.pay(internet.id, ars("1"), TODAY, pesos.id)

        assert charges_notice(services).seen

    def test_a_budget_back_under_its_limit_leaves_the_others_seen(self, services, pesos):
        leisure = budget(services, "Ocio", "10")
        for category in (leisure, budget(services, "Ropa", "10")):
            self.spend(services, pesos, category, "20")
        self.open(services, services.notifications.notices(TODAY)[0])

        services.budgets.set_limit(leisure, Month.of(TODAY), ars("100"))

        assert self.seen(services) == [True]

    def test_a_version_seen_is_kept_while_the_check_has_not_answered(self, services):
        services.notifications.set_release(RELEASE)
        self.open(services, services.notifications.notices(TODAY)[0])

        services.notifications.set_release(None)
        services.notifications.notices(TODAY)  # the bell refreshes before the check answers
        services.notifications.set_release(RELEASE)

        assert self.seen(services) == [True]

    def test_what_no_longer_applies_is_forgotten(self, services, pesos, dollars):
        expense = services.transactions.create(
            expense_draft(services, pesos.id, ars("20"), category_id=budget(services, "Ocio", "10"))
        )
        budget_notice, rate_notice = sorted(
            services.notifications.notices(TODAY), key=lambda n: n.kind.value
        )
        self.open(services, budget_notice)
        services.transactions.delete_many([expense.id])

        self.open(services, rate_notice)
        services.notifications.notices(TODAY)

        assert services.settings.seen_notices() == set(rate_notice.items)
