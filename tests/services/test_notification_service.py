from datetime import timedelta
from decimal import Decimal

from factories import TODAY

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
