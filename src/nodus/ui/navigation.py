"""The application's main sections."""

from enum import Enum


class PageId(Enum):
    """A section reachable from the sidebar. Each value is (label, icon name)."""

    DASHBOARD = ("Dashboard", "dashboard")
    ACCOUNTS = ("Cuentas", "accounts")
    TRANSACTIONS = ("Transacciones", "transactions")
    CATEGORIES = ("Categorías", "categories")
    SETTINGS = ("Ajustes", "settings")

    @property
    def label(self) -> str:
        return self.value[0]

    @property
    def icon_name(self) -> str:
        return self.value[1]
