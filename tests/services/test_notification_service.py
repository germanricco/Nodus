from datetime import timedelta
from decimal import Decimal

from factories import TODAY, ars, category_id, charge_draft, expense_draft

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
    assert notices[0].title == f"Sin cotización desde hace {STALE_RATE_DAYS + 3} días"


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
