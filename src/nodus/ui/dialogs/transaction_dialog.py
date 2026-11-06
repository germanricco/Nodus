"""Dialog to record or edit an expense, an income or a transfer."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from nodus.models.account import Account
from nodus.models.currency import Currency
from nodus.models.exchange_rate import implied_ars_per_usd
from nodus.models.money import Money
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.services.transaction_service import TransactionDraft, TransferDraft
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.date_input import DateInput
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.selectors import AccountComboBox, CategoryComboBox

# Segment order of the mode selector.
EXPENSE_MODE, INCOME_MODE, TRANSFER_MODE = range(3)
MODE_LABELS = ["Gasto", "Ingreso", "Transferencia"]
_MODE_TYPES = {EXPENSE_MODE: TransactionType.EXPENSE, INCOME_MODE: TransactionType.INCOME}


class TransactionDialog(FormDialog):
    """Records a new movement, or edits ``transaction`` when given.

    One form serves the three modes, showing only the fields each needs. A transfer
    between accounts of different currencies also asks for the amount that arrives and
    shows the rate it implies. When editing, an expense can become an income and vice
    versa, but a transfer stays a transfer, since they are stored differently.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        transaction: Transaction | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Editar transacción" if transaction else "Nueva transacción", parent)
        self._services = services
        self._event_bus = event_bus
        self._transaction = transaction

        self.mode_input = SegmentedControl(MODE_LABELS)
        self.add_above_form(self.mode_input)
        self.account_input = AccountComboBox()
        self.to_account_input = AccountComboBox()
        self.amount_input = AmountInput(Currency.ARS)
        self.amount_in_input = AmountInput(Currency.USD)
        self.rate_hint = QLabel()
        self.rate_hint.setObjectName("FieldHint")
        self.category_input = CategoryComboBox()
        self.date_input = DateInput()
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Opcional. Ej.: Supermercado del sábado")

        self.form.addRow("Cuenta", self.account_input)
        self.form.addRow("Hacia", self.to_account_input)
        self.form.addRow("Monto", self.amount_input)
        self.form.addRow("Entra", self.amount_in_input)
        self.form.addRow("", self.rate_hint)
        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("Fecha", self.date_input)
        self.form.addRow("Nota", self.note_input)

        self._load_accounts()
        self.mode_input.changed.connect(self._update_mode)
        self.account_input.currentIndexChanged.connect(self._update_currencies)
        self.to_account_input.currentIndexChanged.connect(self._update_currencies)
        self.amount_input.line_edit.textChanged.connect(self._update_rate_hint)
        self.amount_in_input.line_edit.textChanged.connect(self._update_rate_hint)

        if transaction:
            self._load(transaction)
        else:
            # Most movements go to the same account as the previous one. An archived or
            # deleted account is not in the list, so the first one stays selected.
            self.account_input.select(services.settings.last_account_id())
        self._update_mode()

    @property
    def is_transfer_mode(self) -> bool:
        return self.mode_input.index() == TRANSFER_MODE

    # Loading

    def _load_accounts(self) -> None:
        """Active accounts, plus the archived ones the edited movement already uses."""
        accounts = self._services.accounts.list_accounts()
        if self._transaction:
            used = {leg.account_id for leg in self._legs(self._transaction)}
            active_ids = {account.id for account in accounts}
            accounts += [self._services.accounts.get(i) for i in sorted(used - active_ids)]
        self.account_input.set_accounts(accounts)
        self.to_account_input.set_accounts(accounts)

    def _load(self, transaction: Transaction) -> None:
        if transaction.is_transfer:
            transfer = self._services.transactions.get_transfer(transaction.transfer_id)
            self.mode_input.set_index(TRANSFER_MODE)
            self.mode_input.set_segment_enabled(EXPENSE_MODE, False)
            self.mode_input.set_segment_enabled(INCOME_MODE, False)
            self.account_input.select(transfer.outgoing.account_id)
            self.to_account_input.select(transfer.incoming.account_id)
            self.amount_input.set_money(transfer.outgoing.amount)
            self.amount_in_input.set_money(transfer.incoming.amount)
        else:
            mode = EXPENSE_MODE if transaction.type is TransactionType.EXPENSE else INCOME_MODE
            self.mode_input.set_index(mode)
            self.mode_input.set_segment_enabled(TRANSFER_MODE, False)
            self.account_input.select(transaction.account_id)
            self.amount_input.set_money(transaction.amount)
        self.date_input.set_day(transaction.occurred_on)
        self.note_input.setText(transaction.note)

    def _legs(self, transaction: Transaction) -> list[Transaction]:
        if not transaction.is_transfer:
            return [transaction]
        transfer = self._services.transactions.get_transfer(transaction.transfer_id)
        return [transfer.outgoing, transfer.incoming]

    # Reacting to changes

    def _update_mode(self) -> None:
        transfer = self.is_transfer_mode
        self.form.labelForField(self.account_input).setText("Desde" if transfer else "Cuenta")
        self.form.labelForField(self.amount_input).setText("Sale" if transfer else "Monto")
        self.form.setRowVisible(self.to_account_input, transfer)
        self.form.setRowVisible(self.category_input, not transfer)
        if transfer:
            self._pick_distinct_destination()
        else:
            kind = _MODE_TYPES[self.mode_input.index()]
            self.category_input.set_categories(
                [(None, self._services.categories.category_tree(kind))]
            )
            if self._transaction and not self._transaction.is_transfer:
                self.category_input.select(self._transaction.category_id)
        self._update_currencies()

    def _pick_distinct_destination(self) -> None:
        """For a new transfer, starts with a destination other than the source."""
        source, destination = self.account_input.current_id(), self.to_account_input.current_id()
        if self._transaction or source != destination:
            return
        for index in range(self.to_account_input.count()):
            if self.to_account_input.itemData(index) != source:
                self.to_account_input.setCurrentIndex(index)
                return

    def _update_currencies(self) -> None:
        """Amount fields follow their account's currency; "Entra" only when they differ."""
        source = self.account_input.current_account()
        destination = self.to_account_input.current_account()
        if source:
            self.amount_input.set_currency(source.currency)
        if destination:
            self.amount_in_input.set_currency(destination.currency)
        needs_amount_in = self.is_transfer_mode and _currencies_differ(source, destination)
        self.form.setRowVisible(self.amount_in_input, needs_amount_in)
        self.form.setRowVisible(self.rate_hint, needs_amount_in)
        self._update_rate_hint()

    def _update_rate_hint(self) -> None:
        rate = self._implied_rate()
        self.rate_hint.setText(
            f"Cotización implícita: US$ 1 = {Money.from_decimal(rate, Currency.ARS).format()}"
            if rate is not None
            else "Indica los dos montos para ver la cotización que obtuviste."
        )

    def _implied_rate(self) -> Decimal | None:
        try:
            return implied_ars_per_usd(self.amount_input.money(), self.amount_in_input.money())
        except ValidationError:
            return None

    # Saving

    def save(self) -> None:
        if self.is_transfer_mode:
            self._save_transfer()
        else:
            self._save_transaction()
        self._event_bus.transactions_changed.emit()

    def _save_transaction(self) -> None:
        category_id = self.category_input.current_id()
        if category_id is None:
            raise ValidationError("Elige una categoría.")
        draft = TransactionDraft(
            account_id=self._required_account(self.account_input).id,
            type=_MODE_TYPES[self.mode_input.index()],
            amount=self.amount_input.money(),
            occurred_on=self.date_input.day(),
            category_id=category_id,
            note=self.note_input.text(),
        )
        if self._transaction:
            self._services.transactions.update(self._transaction.id, draft)
        else:
            self._services.transactions.create(draft)
            self._services.settings.set_last_account_id(draft.account_id)

    def _save_transfer(self) -> None:
        source = self._required_account(self.account_input)
        destination = self._required_account(self.to_account_input)
        draft = TransferDraft(
            from_account_id=source.id,
            to_account_id=destination.id,
            amount_out=self.amount_input.money(),
            occurred_on=self.date_input.day(),
            amount_in=(
                self.amount_in_input.money() if _currencies_differ(source, destination) else None
            ),
            note=self.note_input.text(),
        )
        if self._transaction:
            self._services.transactions.update_transfer(self._transaction.transfer_id, draft)
        else:
            self._services.transactions.create_transfer(draft)
            self._services.settings.set_last_account_id(source.id)

    @staticmethod
    def _required_account(combo: AccountComboBox) -> Account:
        account = combo.current_account()
        if account is None:
            raise ValidationError("Elige una cuenta.")
        return account


def _currencies_differ(first: Account | None, second: Account | None) -> bool:
    return bool(first and second and first.currency is not second.currency)
