"""Wiring of services to their repositories."""

from __future__ import annotations

from dataclasses import dataclass

from nodus.database.database import Database
from nodus.database.repositories.account_repository import AccountRepository
from nodus.database.repositories.category_repository import CategoryRepository
from nodus.database.repositories.exchange_rate_repository import ExchangeRateRepository
from nodus.database.repositories.transaction_repository import TransactionRepository
from nodus.services.account_service import AccountService
from nodus.services.category_service import CategoryService
from nodus.services.exchange_rate_service import ExchangeRateService
from nodus.services.transaction_service import TransactionService


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

    @classmethod
    def create(cls, database: Database) -> Services:
        account_repository = AccountRepository(database)
        category_repository = CategoryRepository(database)
        return cls(
            accounts=AccountService(database, account_repository),
            categories=CategoryService(database, category_repository),
            transactions=TransactionService(
                database, TransactionRepository(database), account_repository, category_repository
            ),
            exchange_rates=ExchangeRateService(database, ExchangeRateRepository(database)),
        )
