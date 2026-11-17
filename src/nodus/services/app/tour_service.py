"""When to offer the guided tour: once, to whoever already has an account."""

from __future__ import annotations

from nodus.services.accounts.account_service import AccountService
from nodus.services.app.settings_service import SettingsService


class TourService:
    """Decides whether the guided tour is due and remembers that it was offered."""

    def __init__(self, accounts: AccountService, settings: SettingsService) -> None:
        self._accounts = accounts
        self._settings = settings

    def tour_due(self) -> bool:
        """Whether to offer the guided tour now. A new user gets it right after the
        first account; someone updating, the first time they open this version (after
        its news)."""
        has_accounts = bool(self._accounts.list_accounts(include_archived=True))
        return has_accounts and not self._settings.tour_offered()

    def mark_tour_offered(self) -> None:
        self._settings.set_tour_offered(True)
