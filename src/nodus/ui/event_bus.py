"""Application-wide notifications about data changes."""

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Tells every screen when stored data changed, so each refreshes itself.

    Whoever saves a change (usually a dialog) emits the matching signal; pages and widgets
    that show that data connect to it. No screen needs to know which others exist.
    """

    accounts_changed = Signal()
    categories_changed = Signal()
    transactions_changed = Signal()
    exchange_rates_changed = Signal()
    recurring_changed = Signal()
    budgets_changed = Signal()
    payees_changed = Signal()
    tags_changed = Signal()
    amounts_hidden_changed = Signal(bool)

    def emit_all(self) -> None:
        """Announces that everything may have changed, as after restoring a backup."""
        self.accounts_changed.emit()
        self.categories_changed.emit()
        self.transactions_changed.emit()
        self.exchange_rates_changed.emit()
        self.recurring_changed.emit()
        self.budgets_changed.emit()
        self.payees_changed.emit()
        self.tags_changed.emit()
