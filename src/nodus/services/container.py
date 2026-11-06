"""Wiring of services to their repositories."""

from __future__ import annotations

from dataclasses import dataclass

from nodus import __version__
from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.database.repositories.exchange_rate_repository import ExchangeRateRepository
from nodus.database.repositories.settings_repository import SettingsRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.services.account_service import AccountService
from nodus.services.backup_service import BackupService
from nodus.services.category_service import CategoryService
from nodus.services.dashboard_service import DashboardService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.export_service import ExportService
from nodus.services.net_worth_service import NetWorthService
from nodus.services.settings_service import SettingsService
from nodus.services.transaction_service import TransactionService
from nodus.services.update_service import UpdateService


@dataclass(frozen=True)
class Services:
    """Every service of the application, built once over the same database.

    The UI receives this object instead of creating services itself, which keeps the
    wiring in one place and lets tests build the same graph over a temporary database.
    """

    accounts: AccountService
    categories: CategoryService
    transactions: TransactionService
    exchange_rates: ExchangeRateService
    net_worth: NetWorthService
    settings: SettingsService
    dashboard: DashboardService
    updates: UpdateService
    backups: BackupService
    export: ExportService

    @classmethod
    def create(cls, database: Database) -> Services:
        account_repository = AccountRepository(database)
        category_repository = CategoryRepository(database)
        accounts = AccountService(database, account_repository)
        exchange_rates = ExchangeRateService(database, ExchangeRateRepository(database))
        categories = CategoryService(database, category_repository)
        transactions = TransactionService(
            database, TransactionRepository(database), account_repository, category_repository
        )
        return cls(
            accounts=accounts,
            categories=categories,
            transactions=transactions,
            exchange_rates=exchange_rates,
            net_worth=NetWorthService(accounts, exchange_rates),
            settings=SettingsService(database, SettingsRepository(database)),
            dashboard=DashboardService(transactions, categories, exchange_rates),
            updates=UpdateService(__version__),
            backups=BackupService(database, database.path.parent / "backups"),
            export=ExportService(accounts, categories),
        )
