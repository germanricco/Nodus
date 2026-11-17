"""What Nodus writes to its log as it works says what happened, never the user's data."""

import json
from datetime import date, datetime

import pytest
from factories import ars, usd

from nodus.config.logs import RunLog
from nodus.models.account import AccountType
from nodus.models.currency import Currency
from nodus.services.errors import ValidationError
from nodus.services.external.rate_feed_service import RateFeedService
from nodus.services.external.update_service import UpdateService

NAME = "Caja de Ahorro Galicia"
AMOUNT = "73519"
RATE = 1588.5


@pytest.fixture
def run_log(tmp_path):
    log = RunLog(tmp_path / "logs")
    log.start()
    yield log
    log.stop()


def test_a_day_of_work_leaves_events_without_data(services, database, run_log, tmp_path):
    services.accounts.create(NAME, AccountType.BANK, Currency.ARS, ars(AMOUNT))
    services.accounts.create("Dólares", AccountType.SAVINGS, Currency.USD, usd("0"))
    services.backups.create(date(2026, 11, 17))
    outside = tmp_path / "Pendrive Germán"
    outside.mkdir()
    services.backups.export_to(outside, date(2026, 11, 17))
    services.backups.restore(services.backups.backups_dir / "nodus-2026-11-17.db", datetime.now())
    not_a_copy = tmp_path / f"{NAME}.db"
    not_a_copy.write_text("x")
    with pytest.raises(ValidationError):
        services.backups.restore(not_a_copy, datetime.now())
    quotes = json.dumps([{"casa": "bolsa", "venta": RATE}]).encode()
    feed = RateFeedService(
        services.exchange_rates, services.settings, services.accounts, lambda _url: quotes
    )
    feed.fetch_all("bolsa", [Currency.USD])
    broken = RateFeedService(
        services.exchange_rates,
        services.settings,
        services.accounts,
        lambda _url: b'{"error": "' + NAME.encode() + b'"}',
    )
    broken.fetch_all("bolsa", [Currency.USD])
    UpdateService("1.0.0", lambda _url: b"{}").check()

    text = run_log.log_file.read_text(encoding="utf-8")
    for event in (
        "Backup saved",
        "Copy saved outside the computer",
        "Copy restored",
        "Restore refused",
        "Rates fetched for USD of USD",
        "Dollar rate from bolsa unavailable",
        "Update check failed",
    ):
        assert event in text
    for data in ("Galicia", AMOUNT, "1588", "Germán", "Pendrive", str(tmp_path)):
        assert data not in text
