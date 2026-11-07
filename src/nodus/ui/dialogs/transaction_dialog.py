"""Dialog to record or edit an expense, an income or a transfer."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from nodus.models.account import Account
from nodus.models.currency import Currency
from nodus.models.exchange_rate import ImpliedRate, implied_rate
from nodus.models.payee import Payee
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.services.transaction_service import TransactionDraft, TransferDraft
from nodus.ui.dialogs.account_fields import required_account, selectable_accounts
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.dialogs.refund_picker import RefundField
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import rate_text
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.date_input import DateInput
from nodus.ui.widgets.payee_input import PayeeInput
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.selectors import AccountComboBox, CategoryComboBox
from nodus.ui.widgets.tag_input import TagInput

# Segment order of the mode selector.
EXPENSE_MODE, INCOME_MODE, TRANSFER_MODE = range(3)
MODE_LABELS = ["Gasto", "Ingreso", "Transferencia"]
_MODE_TYPES = {EXPENSE_MODE: TransactionType.EXPENSE, INCOME_MODE: TransactionType.INCOME}
# The default income category for refunds.
REFUNDS_CATEGORY = "Reembolsos"


class TransactionDialog(FormDialog):
    """Records a new movement, or edits ``transaction`` when given.

    One form serves the three modes, showing only the fields each needs. A transfer
    between accounts of different currencies also asks for the amount that arrives and
    shows the rate it implies. When editing, an expense can become an income and vice
    versa, but a transfer stays a transfer, since they are stored differently.

    Choosing a known payee fills in its suggested category, unless the user already
    picked one by hand, which an edited transaction counts as. An income can be linked to
    the expense it pays back; an edited expense shows how much of it was refunded.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        theme_manager: ThemeManager,
        transaction: Transaction | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Editar transacción" if transaction else "Nueva transacción", parent)
        self._services = services
        self._event_bus = event_bus
        self._transaction = transaction
        self._category_picked = transaction is not None

        self.mode_input = SegmentedControl(MODE_LABELS)
        self.add_above_form(self.mode_input)
        self.account_input = AccountComboBox()
        self.to_account_input = AccountComboBox()
        self.amount_input = AmountInput(Currency.ARS)
        self.amount_in_input = AmountInput(Currency.USD)
        self.rate_hint = QLabel()
        self.rate_hint.setObjectName("FieldHint")
        self.payee_input = PayeeInput(services.payees)
        self.category_input = CategoryComboBox()
        self.date_input = DateInput()
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Opcional")
        self.tag_input = TagInput(services.tags)
        self.refund_input = RefundField(
            services, theme_manager, transaction.id if transaction else None
        )
        self.refunded_hint = QLabel()
        self.refunded_hint.setObjectName("FieldHint")

        self.form.addRow("Cuenta", self.account_input)
        self.form.addRow("Hacia", self.to_account_input)
        self.form.addRow("Monto", self.amount_input)
        self.form.addRow("Entra", self.amount_in_input)
        self.form.addRow("", self.rate_hint)
        self.form.addRow("Beneficiario", self.payee_input)
        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("Fecha", self.date_input)
        self.form.addRow("Nota", self.note_input)
        self.form.addRow("Etiquetas", self.tag_input)
        self.form.addRow("Reembolso de", self.refund_input)
        self.form.addRow("", self.refunded_hint)

        self._load_accounts()
        self.mode_input.changed.connect(self._update_mode)
        self.account_input.currentIndexChanged.connect(self._update_currencies)
        self.to_account_input.currentIndexChanged.connect(self._update_currencies)
        self.amount_input.line_edit.textChanged.connect(self._update_rate_hint)
        self.amount_in_input.line_edit.textChanged.connect(self._update_rate_hint)
        self.payee_input.payee_chosen.connect(self._suggest_category)
        self.category_input.activated.connect(self._mark_category_picked)
        self.refund_input.changed.connect(self._suggest_refund_category)

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
        used = (
            [leg.account_id for leg in self._legs(self._transaction)] if self._transaction else []
        )
        accounts = selectable_accounts(self._services, used)
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
            if transaction.payee_id is not None:
                self.payee_input.set_text(self._services.payees.get(transaction.payee_id).name)
            tags = self._services.transactions.tags_for([transaction.id])
            self.tag_input.set_names([tag.name for tag in tags.get(transaction.id, [])])
            if transaction.refund_of_id is not None:
                self.refund_input.set_expense(
                    self._services.transactions.get(transaction.refund_of_id)
                )
            self._show_refunded(transaction)
        self.date_input.set_day(transaction.occurred_on)
        self.note_input.setText(transaction.note)

    def _show_refunded(self, transaction: Transaction) -> None:
        """ "Reembolsado $ 400,00 de $ 1.000,00", for an expense with refunds."""
        summary = self._services.transactions.refund_summary(transaction.id)
        if summary.refunds:
            self.refunded_hint.setText(
                f"Reembolsado {summary.refunded.format()} de {transaction.amount.format()}"
            )

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
        self.form.setRowVisible(self.payee_input, not transfer)
        self.form.setRowVisible(self.category_input, not transfer)
        self.form.setRowVisible(self.tag_input, not transfer)
        income = self.mode_input.index() == INCOME_MODE
        self.form.setRowVisible(self.refund_input, income)
        expense = self.mode_input.index() == EXPENSE_MODE
        self.form.setRowVisible(self.refunded_hint, expense and bool(self.refunded_hint.text()))
        if transfer:
            self._pick_distinct_destination()
        else:
            kind = _MODE_TYPES[self.mode_input.index()]
            self.category_input.set_categories(
                [(None, self._services.categories.category_tree(kind))]
            )
            if self._transaction and not self._transaction.is_transfer:
                self.category_input.select(self._transaction.category_id)
            payee = self._services.payees.find(self.payee_input.text())
            if payee is not None:
                self._suggest_category(payee)
        self._update_currencies()

    def _mark_category_picked(self) -> None:
        self._category_picked = True

    def _suggest_category(self, payee: Payee) -> None:
        if self._category_picked or self.is_transfer_mode:
            return
        kind = _MODE_TYPES[self.mode_input.index()]
        category_id = self._services.payees.suggested_category(payee.id, kind)
        if category_id is not None:
            self.category_input.select(category_id)

    def _suggest_refund_category(self) -> None:
        """A refund goes to the "Reembolsos" income category, unless one was picked."""
        if self._category_picked or self.refund_input.expense_id() is None:
            return
        for category in self._services.categories.list_categories(TransactionType.INCOME):
            if category.name == REFUNDS_CATEGORY:
                self.category_input.select(category.id)
                return

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
        self._update_rate_hint()

    def _update_rate_hint(self) -> None:
        """Shows the rate the transfer implies, once both amounts are filled in."""
        rate = self._implied_rate() if self.form.isRowVisible(self.amount_in_input) else None
        if rate is not None:
            text = rate_text(rate.base, rate.quote, rate.value)
            self.rate_hint.setText(f"Cotización implícita: {text}")
        self.form.setRowVisible(self.rate_hint, rate is not None)

    def _implied_rate(self) -> ImpliedRate | None:
        try:
            return implied_rate(self.amount_input.money(), self.amount_in_input.money())
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
            account_id=required_account(self.account_input).id,
            type=_MODE_TYPES[self.mode_input.index()],
            amount=self.amount_input.money(),
            occurred_on=self.date_input.day(),
            category_id=category_id,
            note=self.note_input.text(),
            payee_name=self.payee_input.text(),
            refund_of_id=self.refund_input.expense_id(),
            tag_names=self.tag_input.names(),
        )
        creates_tags = any(self._services.tags.find(name) is None for name in draft.tag_names)
        if self._transaction:
            self._services.transactions.update(self._transaction.id, draft)
        else:
            self._services.transactions.create(draft)
            self._services.settings.set_last_account_id(draft.account_id)
        if creates_tags:
            self._event_bus.tags_changed.emit()

    def _save_transfer(self) -> None:
        source = required_account(self.account_input)
        destination = required_account(self.to_account_input)
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


def _currencies_differ(first: Account | None, second: Account | None) -> bool:
    return bool(first and second and first.currency is not second.currency)
