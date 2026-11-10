"""Wiring of services to their repositories."""

from __future__ import annotations

from dataclasses import dataclass

from nodus import __version__
from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.budget_repository import BudgetRepository
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.database.repositories.exchange_rate_repository import ExchangeRateRepository
from nodus.database.repositories.installment_plan_repository import InstallmentPlanRepository
from nodus.database.repositories.payee_repository import PayeeRepository
from nodus.database.repositories.recurring_charge_repository import RecurringChargeRepository
from nodus.database.repositories.settings_repository import SettingsRepository
from nodus.database.repositories.tag_repository import TagRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.database.repositories.value_adjustment_repository import ValueAdjustmentRepository
from nodus.services.account_service import AccountService
from nodus.services.analysis_service import AnalysisService
from nodus.services.backup_service import BackupService
from nodus.services.budget_service import BudgetService
from nodus.services.category_service import CategoryService
from nodus.services.dashboard_service import DashboardService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.export_service import ExportService
from nodus.services.http import downloader
from nodus.services.installment_service import InstallmentService
from nodus.services.net_worth_service import NetWorthService
from nodus.services.news_service import NewsService
from nodus.services.notification_service import NotificationService
from nodus.services.payee_service import PayeeService
from nodus.services.rate_feed_service import RateFeedService
from nodus.services.recurring_charge_service import RecurringChargeService
from nodus.services.settings_service import SettingsService
from nodus.services.startup_service import StartupService
from nodus.services.tag_service import TagService
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
    rate_feed: RateFeedService
    notifications: NotificationService
    recurring: RecurringChargeService
    installments: InstallmentService
    budgets: BudgetService
    payees: PayeeService
    analysis: AnalysisService
    tags: TagService
    startup: StartupService
    news: NewsService

    @classmethod
    def create(cls, database: Database) -> Services:
        account_repository = AccountRepository(database)
        category_repository = CategoryRepository(database)
        accounts = AccountService(database, account_repository, ValueAdjustmentRepository(database))
        exchange_rates = ExchangeRateService(database, ExchangeRateRepository(database))
        categories = CategoryService(database, category_repository)
        transaction_repository = TransactionRepository(database)
        payee_repository = PayeeRepository(database)
        tag_repository = TagRepository(database)
        transactions = TransactionService(
            database,
            transaction_repository,
            account_repository,
            category_repository,
            payee_repository,
            tag_repository,
        )
        payees = PayeeService(database, payee_repository, transactions, categories, exchange_rates)
        recurring = RecurringChargeService(
            database,
            RecurringChargeRepository(database),
            transaction_repository,
            transactions,
            accounts,
            exchange_rates,
        )
        settings = SettingsService(database, SettingsRepository(database))
        backups = BackupService(database, database.path.parent / "backups")
        dashboard = DashboardService(transactions, categories, exchange_rates)
        budgets = BudgetService(database, BudgetRepository(database), categories, dashboard)
        return cls(
            accounts=accounts,
            categories=categories,
            transactions=transactions,
            exchange_rates=exchange_rates,
            net_worth=NetWorthService(accounts, transactions, exchange_rates),
            settings=settings,
            dashboard=dashboard,
            updates=UpdateService.for_this_program(__version__),
            backups=backups,
            export=ExportService(accounts, categories, payees, transactions),
            rate_feed=RateFeedService(
                exchange_rates, settings, accounts, downloader(f"Nodus/{__version__}")
            ),
            notifications=NotificationService(
                settings, accounts, exchange_rates, backups, recurring, budgets
            ),
            recurring=recurring,
            installments=InstallmentService(
                database, InstallmentPlanRepository(database), transaction_repository, transactions
            ),
            budgets=budgets,
            payees=payees,
            analysis=AnalysisService(transactions, categories, payees, exchange_rates),
            tags=TagService(database, tag_repository, transactions, exchange_rates),
            startup=StartupService.for_this_program(),
            news=NewsService(settings, __version__, first_start=database.created),
        )
