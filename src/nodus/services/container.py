"""Wiring of services to their repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nodus import USER_AGENT, __version__
from nodus.database.database import Database
from nodus.database.repositories.account_group_repository import AccountGroupRepository
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.budget_repository import BudgetRepository
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.database.repositories.exchange_rate_repository import ExchangeRateRepository
from nodus.database.repositories.goal_repository import GoalRepository
from nodus.database.repositories.installment_plan_repository import InstallmentPlanRepository
from nodus.database.repositories.payee_repository import PayeeRepository
from nodus.database.repositories.recurring_charge_repository import RecurringChargeRepository
from nodus.database.repositories.settings_repository import SettingsRepository
from nodus.database.repositories.tag_repository import TagRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.database.repositories.value_adjustment_repository import ValueAdjustmentRepository
from nodus.services.accounts.account_group_service import AccountGroupService
from nodus.services.accounts.account_service import AccountService
from nodus.services.accounts.exchange_rate_service import ExchangeRateService
from nodus.services.app.news_service import NewsService
from nodus.services.app.notification_service import NotificationService
from nodus.services.app.seen_service import SeenService
from nodus.services.app.settings_service import SettingsService
from nodus.services.app.tour_service import TourService
from nodus.services.app.undo_service import UndoService
from nodus.services.backups.backup_service import BackupService
from nodus.services.classification.category_service import CategoryService
from nodus.services.classification.payee_service import PayeeService
from nodus.services.classification.tag_service import TagService
from nodus.services.external.http import downloader
from nodus.services.external.rate_feed_service import RateFeedService
from nodus.services.external.startup_service import StartupService
from nodus.services.external.update_service import UpdateService
from nodus.services.planning.budget_service import BudgetService
from nodus.services.planning.goal_service import GoalService
from nodus.services.reports.analysis_service import AnalysisService
from nodus.services.reports.dashboard_service import DashboardService
from nodus.services.reports.export_service import ExportService
from nodus.services.reports.net_worth_service import NetWorthService
from nodus.services.transactions.bulk_edit_service import BulkEditService
from nodus.services.transactions.installment_service import InstallmentService
from nodus.services.transactions.labels import MovementLabels
from nodus.services.transactions.recurring_charge_service import RecurringChargeService
from nodus.services.transactions.refund_service import RefundService
from nodus.services.transactions.transaction_service import TransactionService
from nodus.services.transactions.transfer_service import TransferService


@dataclass(frozen=True)
class Services:
    """Every service of the application, built once over the same database.

    The UI receives this object instead of creating services itself, which keeps the
    wiring in one place and lets tests build the same graph over a temporary database.
    """

    accounts: AccountService
    account_groups: AccountGroupService
    goals: GoalService
    categories: CategoryService
    transactions: TransactionService
    transfers: TransferService
    refunds: RefundService
    bulk_edits: BulkEditService
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
    tour: TourService
    undo: UndoService

    @classmethod
    def create(cls, database: Database, backups_dir: Path) -> Services:
        undo = UndoService(database)
        settings = SettingsService(database, SettingsRepository(database))
        backups = BackupService(database, backups_dir, settings, undo)
        account_repository = AccountRepository(database)
        category_repository = CategoryRepository(database)
        accounts = AccountService(
            database, account_repository, ValueAdjustmentRepository(database), backups
        )
        exchange_rates = ExchangeRateService(database, ExchangeRateRepository(database))
        categories = CategoryService(database, category_repository, backups)
        if database.created:
            categories.name_defaults()
        transaction_repository = TransactionRepository(database)
        payee_repository = PayeeRepository(database)
        tag_repository = TagRepository(database)
        labels = MovementLabels(payee_repository, tag_repository)
        refunds = RefundService(transaction_repository)
        transactions = TransactionService(
            database,
            transaction_repository,
            account_repository,
            category_repository,
            tag_repository,
            labels,
            refunds,
            backups,
        )
        payees = PayeeService(
            database, payee_repository, transactions, categories, exchange_rates, undo
        )
        seen = SeenService(settings)
        recurring = RecurringChargeService(
            database,
            RecurringChargeRepository(database),
            transaction_repository,
            transactions,
            accounts,
            exchange_rates,
            undo,
            seen,
        )
        dashboard = DashboardService(transactions, categories, exchange_rates)
        budgets = BudgetService(
            database, BudgetRepository(database), categories, dashboard, transactions
        )
        goals = GoalService(database, GoalRepository(database), accounts, exchange_rates)
        return cls(
            accounts=accounts,
            goals=goals,
            account_groups=AccountGroupService(
                database,
                AccountGroupRepository(database),
                account_repository,
                accounts,
                exchange_rates,
                settings,
                undo,
            ),
            categories=categories,
            transactions=transactions,
            transfers=TransferService(database, transaction_repository, account_repository),
            refunds=refunds,
            bulk_edits=BulkEditService(
                database,
                transaction_repository,
                category_repository,
                payee_repository,
                tag_repository,
                labels,
                undo,
            ),
            exchange_rates=exchange_rates,
            net_worth=NetWorthService(accounts, transactions, exchange_rates),
            settings=settings,
            dashboard=dashboard,
            updates=UpdateService.for_this_program(__version__),
            backups=backups,
            export=ExportService(accounts, categories, payees, transactions),
            rate_feed=RateFeedService(exchange_rates, settings, accounts, downloader(USER_AGENT)),
            notifications=NotificationService(
                settings, seen, accounts, exchange_rates, backups, recurring, budgets, goals
            ),
            recurring=recurring,
            installments=InstallmentService(
                database,
                InstallmentPlanRepository(database),
                transaction_repository,
                transactions,
                undo,
            ),
            budgets=budgets,
            payees=payees,
            analysis=AnalysisService(transactions, categories, payees, exchange_rates),
            tags=TagService(database, tag_repository, transactions, exchange_rates, undo),
            startup=StartupService.for_this_program(),
            news=NewsService(settings, __version__, first_start=database.created),
            tour=TourService(accounts, settings),
            undo=undo,
        )
