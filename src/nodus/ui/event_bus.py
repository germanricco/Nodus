"""Application-wide notifications about data changes."""

from PySide6.QtCore import QObject, Signal, SignalInstance


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
    goals_changed = Signal()
    backups_changed = Signal()
    amounts_hidden_changed = Signal(bool)
    # The currency totals are converted to (the net worth's) changed.
    net_worth_currency_changed = Signal()

    def data_signals(self) -> list[SignalInstance]:
        """Every signal about stored data, for a change that may touch any of it."""
        return [
            self.accounts_changed,
            self.categories_changed,
            self.transactions_changed,
            self.exchange_rates_changed,
            self.recurring_changed,
            self.budgets_changed,
            self.payees_changed,
            self.tags_changed,
            self.goals_changed,
            self.backups_changed,
        ]

    def emit_all(self) -> None:
        """Announces that everything may have changed, as after restoring a backup."""
        for signal in self.data_signals():
            signal.emit()
