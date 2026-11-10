"""Dialog to record or edit an expense, an income or a transfer."""

from __future__ import annotations

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from nodus.models.account import Account
from nodus.models.currency import Currency
from nodus.models.exchange_rate import ImpliedRate, implied_rate
from nodus.models.payee import Payee
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.services.transaction_service import TransactionDraft, TransferDraft
from nodus.ui.dialogs.account_fields import required_account, selectable_accounts
from nodus.ui.dialogs.form_dialog import (
    ACCOUNT_PLACEHOLDER,
    CATEGORY_PLACEHOLDER,
    CHOOSE_ACCOUNT,
    CHOOSE_CATEGORY,
    SAVE_CHANGES,
    TYPE_AMOUNT,
    FormDialog,
)
from nodus.ui.dialogs.installment_fields import ASK_COUNT, InstallmentFields
from nodus.ui.dialogs.refund_picker import RefundField
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import rate_text
from nodus.ui.theme.design import Space
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
FIRST_INSTALLMENT_LABEL = "Primera cuota"
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

    An expense can be paid in installments («Cuotas»). Opening any installment edits the
    whole purchase, which stays an expense.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        theme_manager: ThemeManager,
        transaction: Transaction | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Editar transacción" if transaction else "Nueva transacción",
            parent,
            SAVE_CHANGES if transaction else "Agregar transacción",
        )
        self._services = services
        self._event_bus = event_bus
        self._transaction = transaction
        self._category_picked = transaction is not None

        self.mode_input = SegmentedControl(MODE_LABELS)
        self.add_above_form(self.mode_input)
        # Nothing stands chosen that the user did not choose: only the account comes
        # filled in, with the last one used.
        self.account_input = AccountComboBox()
        self.account_input.set_placeholder(ACCOUNT_PLACEHOLDER)
        self.to_account_input = AccountComboBox()
        self.to_account_input.set_placeholder(ACCOUNT_PLACEHOLDER)
        self.amount_input = AmountInput(Currency.ARS)
        self.amount_in_input = AmountInput(Currency.USD)
        self.installment_fields = InstallmentFields()
        self.installments_hint = QLabel()
        self.installments_hint.setObjectName("FieldHint")
        self.installments_hint.setWordWrap(True)  # a long hint wraps; it never widens
        self.installments_hint.hide()
        self.rate_hint = QLabel()
        self.rate_hint.setObjectName("FieldHint")
        self.payee_input = PayeeInput(services.payees)
        self.category_input = CategoryComboBox()
        self.category_input.set_placeholder(CATEGORY_PLACEHOLDER)
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
        # How it is paid before how much: the amount then reads as the total or as one
        # installment, and what the installments come to is said once, under it.
        self.form.addRow("Cuotas", self.installment_fields)
        # «Total | Por cuota» says how to read the amount, so it goes next to it, and
        # the hint right under it.
        self.amount_row = QWidget()
        amount_layout = QVBoxLayout(self.amount_row)
        amount_layout.setContentsMargins(0, 0, 0, 0)
        amount_layout.setSpacing(Space.XS)
        amount_line = QHBoxLayout()
        amount_line.setSpacing(Space.S)
        amount_line.addWidget(self.amount_input, stretch=1)
        amount_line.addWidget(self.installment_fields.amount_mode)
        amount_layout.addLayout(amount_line)
        amount_layout.addWidget(self.installments_hint)
        self.form.addRow("Monto", self.amount_row)
        self.form.addRow("Entra", self.amount_in_input)
        self.form.addRow("", self.rate_hint)
        self.form.addRow("Beneficiario", self.payee_input)
        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("Fecha", self.date_input)
        self.form.addRow("Nota", self.note_input)
        self.form.addRow("Etiquetas", self.tag_input)
        self.form.addRow("Reembolso de", self.refund_input)
        self.form.addRow("", self.refunded_hint)

        # The names the services give these fields in their errors.
        self.bind_field(self.account_input, "account_id", "from_account_id")
        self.bind_field(self.to_account_input, "to_account_id")
        self.bind_field(self.amount_input, "amount", "amount_out")
        self.bind_field(self.amount_in_input, "amount_in")
        self.bind_field(self.category_input, "category_id")

        self._load_accounts()
        self.mode_input.changed.connect(self._update_mode)
        self.account_input.currentIndexChanged.connect(self._update_currencies)
        self.to_account_input.currentIndexChanged.connect(self._update_currencies)
        self.amount_input.line_edit.textChanged.connect(self._update_rate_hint)
        self.amount_in_input.line_edit.textChanged.connect(self._update_rate_hint)
        self.payee_input.payee_chosen.connect(self._suggest_category)
        self.category_input.activated.connect(self._category_chosen)
        self.category_input.currentIndexChanged.connect(self._update_refund_row)
        self.refund_input.changed.connect(self._update_refund_row)
        self.installment_fields.changed.connect(self._update_installments)
        self.amount_input.line_edit.textChanged.connect(self._update_installments)
        self.date_input.dateChanged.connect(self._update_installments)

        if transaction:
            self._load(transaction)
        else:
            # Most movements go to the same account as the previous one.
            self.account_input.offer(services.settings.last_account_id())
        self._update_mode()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """Sizes the dialog for its widest look, so it keeps its width while installments
        come and go: the amount with «Total | Por cuota», and the labels with «Primera
        cuota». Measured here, once the style sheet has sized everything."""
        self.ensurePolished()
        switch = self.installment_fields.amount_mode
        hidden = switch.isHidden()
        switch.show()
        self.amount_row.setMinimumWidth(self.amount_row.sizeHint().width())
        switch.setHidden(hidden)
        self.form.labelForField(self.date_input).setText(FIRST_INSTALLMENT_LABEL)
        super().showEvent(event)  # gives every label the width of the longest
        self._update_installments()
        # The amount is what is always typed, so it is ready for the keyboard.
        self.amount_input.line_edit.setFocus()
        self.amount_input.line_edit.selectAll()

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
            if transaction.installment is not None:
                self._load_purchase(transaction)
                return
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

    def _load_purchase(self, installment: Transaction) -> None:
        """An installment opens its whole purchase: the total, the count and the first day.
        A purchase stays an expense."""
        plan = self._services.installments.plan(installment.installment.plan_id)
        self.mode_input.set_segment_enabled(INCOME_MODE, False)
        self.amount_input.set_money(plan.total)
        self.installment_fields.set_plan(plan)
        if installment.payee_id is not None:
            self.payee_input.set_text(self._services.payees.get(installment.payee_id).name)
        tags = self._services.transactions.tags_for([installment.id])
        self.tag_input.set_names([tag.name for tag in tags.get(installment.id, [])])
        self.date_input.set_day(plan.first_due_on)
        self.note_input.setText(installment.note)

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
        self.form.setRowVisible(self.to_account_input, transfer)
        self.form.setRowVisible(self.payee_input, not transfer)
        self.form.setRowVisible(self.category_input, not transfer)
        self.form.setRowVisible(self.tag_input, not transfer)
        expense = self.mode_input.index() == EXPENSE_MODE
        self.form.setRowVisible(self.refunded_hint, expense and bool(self.refunded_hint.text()))
        self.form.setRowVisible(self.installment_fields, expense)
        if not transfer:
            kind = _MODE_TYPES[self.mode_input.index()]
            self.category_input.set_categories(
                [(None, self._services.categories.category_tree(kind))]
            )
            if self._transaction and not self._transaction.is_transfer:
                self.category_input.select(self._transaction.category_id)
            payee = self._services.payees.find(self.payee_input.text())
            if payee is not None:
                self._suggest_category(payee)
        self._update_refund_row()
        self._update_currencies()
        self._update_installments()

    def _update_refund_row(self) -> None:
        """«Reembolso de» only for a refund: an income in «Reembolsos», or one already
        linked to an expense."""
        income = self.mode_input.index() == INCOME_MODE
        linked = self.refund_input.expense_id() is not None
        self.form.setRowVisible(self.refund_input, income and (self._is_refund() or linked))

    def _is_refund(self) -> bool:
        chosen = self.category_input.current_id()
        return chosen is not None and chosen == self._refunds_category_id()

    def _category_chosen(self) -> None:
        """The user picked a category: it is kept over the payee's, and leaving
        «Reembolsos» drops the link to an expense, so no hidden link is ever saved."""
        self._category_picked = True
        if not self._is_refund():
            self.refund_input.set_expense(None)
        self._update_refund_row()

    def _refunds_category_id(self) -> int | None:
        return next(
            (
                category.id
                for category in self._services.categories.list_categories(TransactionType.INCOME)
                if category.name == REFUNDS_CATEGORY
            ),
            None,
        )

    def _update_installments(self) -> None:
        """Names «Monto» and «Fecha» for what they are in a purchase in installments, and
        shows what the installments come to."""
        fields = self.installment_fields
        in_installments = self.mode_input.index() == EXPENSE_MODE and fields.in_installments
        fields.amount_mode.setVisible(in_installments)
        amount_label = "Monto"
        if in_installments:
            amount_label = "Cuota" if fields.is_per_installment else "Total"
        elif self.is_transfer_mode:
            amount_label = "Sale"
        self.form.labelForField(self.amount_row).setText(amount_label)
        self.form.labelForField(self.date_input).setText(
            FIRST_INSTALLMENT_LABEL if in_installments else "Fecha"
        )
        try:
            amount = self.amount_input.money()
        except ValidationError:
            amount = None
        hint = fields.hint_text(amount, self.date_input.day()) if in_installments else None
        self.installments_hint.setText(hint or "")
        self.installments_hint.setVisible(hint is not None)

    def _suggest_category(self, payee: Payee) -> None:
        if self._category_picked or self.is_transfer_mode:
            return
        kind = _MODE_TYPES[self.mode_input.index()]
        category_id = self._services.payees.suggested_category(payee.id, kind)
        if category_id is not None:
            self.category_input.select(category_id)

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

    def missing(self) -> dict[QWidget, str]:
        """What each mode needs: rows the mode hides are left out by ``required``."""
        fields = self.installment_fields
        return self.required(
            (self.account_input, CHOOSE_ACCOUNT),
            (self.to_account_input, "Elige la cuenta de destino."),
            (fields.other_input if fields.is_other else fields.count_input, ASK_COUNT),
            (self.amount_input, TYPE_AMOUNT),
            (self.amount_in_input, "Escribe el monto que entra."),
            (self.category_input, CHOOSE_CATEGORY),
        )

    def save(self) -> None:
        if self.is_transfer_mode:
            self._save_transfer()
        else:
            self._save_transaction()
        self._event_bus.transactions_changed.emit()

    def _save_transaction(self) -> None:
        category_id = self.category_input.current_id()
        assert category_id is not None  # ``missing`` asks for it first
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
        plan = (
            self.installment_fields.plan_for(draft.amount, draft.occurred_on)
            if draft.type is TransactionType.EXPENSE
            else None
        )
        installments = self._services.installments
        if self._transaction and (plan or self._transaction.installment):
            installments.update(self._transaction.id, draft, plan)
        elif self._transaction:
            self._services.transactions.update(self._transaction.id, draft)
        else:
            if plan:
                installments.create(draft, plan)
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
