"""Dialog to record or edit an expense, an income or a transfer."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from nodus.i18n import N_, _
from nodus.models.account import Account
from nodus.models.currency import HOME_CURRENCY, Currency
from nodus.models.exchange_rate import ImpliedRate, implied_rate
from nodus.models.payee import Payee
from nodus.models.transaction import Transaction, TransactionType
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.services.transactions.transaction_service import TransactionDraft
from nodus.services.transactions.transfer_service import TransferDraft
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
from nodus.ui.dialogs.installment_fields import InstallmentFields, ask_count
from nodus.ui.dialogs.refund_extra_dialog import RefundExtraDialog
from nodus.ui.dialogs.refund_picker import RefundField
from nodus.ui.event_bus import EventBus
from nodus.ui.text.labels import rate_text
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.inputs.amount_input import AmountInput
from nodus.ui.widgets.inputs.date_input import DateInput
from nodus.ui.widgets.inputs.payee_input import PayeeInput
from nodus.ui.widgets.inputs.segmented import SegmentedControl
from nodus.ui.widgets.inputs.selectors import AccountComboBox, CategoryComboBox
from nodus.ui.widgets.inputs.tag_input import TagInput
from nodus.ui.widgets.style import hint_label

# Segment order of the mode selector.
EXPENSE_MODE, INCOME_MODE, TRANSFER_MODE = range(3)
MODE_LABELS = [N_("Gasto"), N_("Ingreso"), N_("Transferencia")]
FIRST_INSTALLMENT_LABEL = N_("Primera cuota")
_MODE_TYPES = {EXPENSE_MODE: TransactionType.EXPENSE, INCOME_MODE: TransactionType.INCOME}
# The default income category for refunds.


@dataclass(frozen=True)
class TransactionStart:
    """What a new movement starts with when it is added from a page about one account,
    category, payee or tag: that item, already in its field. A category also sets the
    kind of movement, expense or income.

    ``copy_of`` starts it as a copy of a movement («Duplicar»): its kind, accounts,
    amount, payee, category, tags and note, dated today. Never an installment, which
    belongs to a purchase."""

    account_id: int | None = None
    payee: str = ""
    tag: str = ""
    category_id: int | None = None
    copy_of: Transaction | None = None


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
        start: TransactionStart | None = None,
    ) -> None:
        super().__init__(
            _("Editar transacción") if transaction else _("Nueva transacción"),
            parent,
            _(SAVE_CHANGES) if transaction else _("Agregar transacción"),
        )
        self._services = services
        self._event_bus = event_bus
        self._transaction = transaction
        self._category_picked = transaction is not None
        # The category the form keeps through changes of mode: the edited or copied one's.
        self._kept_category_id = (
            transaction.category_id if transaction and not transaction.is_transfer else None
        )
        self._create_fields(services, theme_manager, transaction)
        self._lay_out()
        self._connect()
        self._load_accounts()
        if transaction:
            self._load(transaction)
        else:
            self._start(start or TransactionStart())
        self._update_mode()

    def _create_fields(
        self, services: Services, theme_manager: ThemeManager, transaction: Transaction | None
    ) -> None:
        self.mode_input = SegmentedControl([_(label) for label in MODE_LABELS])
        self.add_above_form(self.mode_input)
        # Nothing stands chosen that the user did not choose: only the account comes
        # filled in, with the last one used.
        self.account_input = AccountComboBox()
        self.account_input.set_placeholder(_(ACCOUNT_PLACEHOLDER))
        self.to_account_input = AccountComboBox()
        self.to_account_input.set_placeholder(_(ACCOUNT_PLACEHOLDER))
        self.amount_input = AmountInput(HOME_CURRENCY)
        self.amount_in_input = AmountInput(Currency.USD)
        self.installment_fields = InstallmentFields()
        self.installments_hint = hint_label()
        self.installments_hint.setWordWrap(True)  # a long hint wraps; it never widens
        self.installments_hint.hide()
        self.rate_hint = hint_label()
        self.payee_input = PayeeInput(services.payees, self._payee_context)
        self.category_input = CategoryComboBox()
        self.category_input.set_placeholder(_(CATEGORY_PLACEHOLDER))
        self.date_input = DateInput()
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText(_("Opcional"))
        self.tag_input = TagInput(services.tags)
        self.refund_input = RefundField(
            services, theme_manager, transaction.id if transaction else None
        )
        self.refunded_hint = hint_label()

    def _lay_out(self) -> None:
        self.form.addRow(_("Cuenta"), self.account_input)
        self.form.addRow(_("Hacia"), self.to_account_input)
        # How it is paid before how much: the amount then reads as the total or as one
        # installment, and what the installments come to is said once, under it.
        self.form.addRow(_("Cuotas"), self.installment_fields)
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
        self.form.addRow(_("Monto"), self.amount_row)
        self.form.addRow(_("Entra"), self.amount_in_input)
        self.form.addRow("", self.rate_hint)
        self.form.addRow(_("Beneficiario"), self.payee_input)
        self.form.addRow(_("Categoría"), self.category_input)
        self.form.addRow(_("Fecha"), self.date_input)
        self.form.addRow(_("Nota"), self.note_input)
        self.form.addRow(_("Etiquetas"), self.tag_input)
        self.form.addRow(_("Reembolso de"), self.refund_input)
        self.form.addRow("", self.refunded_hint)

        # The names the services give these fields in their errors.
        self.bind_field(self.account_input, "account_id", "from_account_id")
        self.bind_field(self.to_account_input, "to_account_id")
        self.bind_field(self.amount_input, "amount", "amount_out")
        self.bind_field(self.amount_in_input, "amount_in")
        self.bind_field(self.category_input, "category_id")

    def _connect(self) -> None:
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
        self.form.labelForField(self.date_input).setText(_(FIRST_INSTALLMENT_LABEL))
        super().showEvent(event)  # gives every label the width of the longest
        self._update_installments()
        # The amount is what is always typed, so it is ready for the keyboard.
        self.amount_input.line_edit.setFocus()
        self.amount_input.line_edit.selectAll()

    def _start(self, start: TransactionStart) -> None:
        """Fills what the page it was opened from already knows; otherwise the account is
        the last one used, where most movements go."""
        if start.copy_of is not None:
            self._copy(start.copy_of)
            return
        self.account_input.offer(start.account_id or self._services.settings.last_account_id())
        if start.payee:
            self.payee_input.set_text(start.payee)
            payee = self._services.payees.find(start.payee)
            if payee is not None:
                self._suggest_category(payee)
        if start.tag:
            self.tag_input.set_names([start.tag])
        if start.category_id is not None:
            category = self._services.categories.get(start.category_id)
            income = category.kind is TransactionType.INCOME
            self.mode_input.set_index(INCOME_MODE if income else EXPENSE_MODE)
            self.category_input.select(category.id)
            self._category_picked = True

    def _payee_context(self) -> tuple[TransactionType | None, int | None]:
        """The kind and category the payee suggestions follow; none for a transfer."""
        if self.is_transfer_mode:
            return None, None
        return _MODE_TYPES[self.mode_input.index()], self.category_input.current_id()

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
            transfer = self._services.transfers.get(transaction.transfer_id)
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

    def _copy(self, original: Transaction) -> None:
        """Everything of ``original`` but its day: a copy is dated today."""
        if original.is_transfer:
            transfer = self._services.transfers.get(original.transfer_id)
            self.mode_input.set_index(TRANSFER_MODE)
            self.account_input.offer(transfer.outgoing.account_id)
            self.to_account_input.select(transfer.incoming.account_id)
            self.amount_input.set_money(transfer.outgoing.amount)
            self.amount_in_input.set_money(transfer.incoming.amount)
        else:
            income = original.type is TransactionType.INCOME
            self._kept_category_id = original.category_id
            self._category_picked = True
            self.mode_input.set_index(INCOME_MODE if income else EXPENSE_MODE)
            self.account_input.offer(original.account_id)
            self.amount_input.set_money(original.amount)
            self.category_input.select(original.category_id)
            if original.payee_id is not None:
                self.payee_input.set_text(self._services.payees.get(original.payee_id).name)
            tags = self._services.transactions.tags_for([original.id])
            self.tag_input.set_names([tag.name for tag in tags.get(original.id, [])])
        self.note_input.setText(original.note)

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
        summary = self._services.refunds.summary(transaction.id)
        if summary.refunds:
            self.refunded_hint.setText(
                _("Reembolsado {refunded} de {amount}").format(
                    refunded=summary.refunded.format(), amount=transaction.amount.format()
                )
            )

    def _legs(self, transaction: Transaction) -> list[Transaction]:
        if not transaction.is_transfer:
            return [transaction]
        transfer = self._services.transfers.get(transaction.transfer_id)
        return [transfer.outgoing, transfer.incoming]

    # Reacting to changes

    def _update_mode(self) -> None:
        transfer = self.is_transfer_mode
        self.form.labelForField(self.account_input).setText(_("Desde") if transfer else _("Cuenta"))
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
            if self._kept_category_id is not None:
                self.category_input.select(self._kept_category_id)
            payee = self._services.payees.find(self.payee_input.text())
            if payee is not None:
                self._suggest_category(payee)
        self._update_refund_row()
        self._update_currencies()
        self._update_installments()

    def _update_refund_row(self) -> None:
        """«Reembolso de» only for a refund: an income in the refunds category, or one
        already linked to an expense."""
        income = self.mode_input.index() == INCOME_MODE
        linked = self.refund_input.expense_id() is not None
        self.form.setRowVisible(self.refund_input, income and (self._is_refund() or linked))

    def _is_refund(self) -> bool:
        chosen = self.category_input.current_id()
        return chosen is not None and chosen == self._refunds_category_id()

    def _category_chosen(self) -> None:
        """The user picked a category: it is kept over the payee's, and leaving the refunds
        category drops the link to an expense, so no hidden link is ever saved."""
        self._category_picked = True
        if not self._is_refund():
            self.refund_input.set_expense(None)
        self._update_refund_row()

    def _refunds_category_id(self) -> int:
        return self._services.categories.refunds_category().id

    def _update_installments(self) -> None:
        """Names «Monto» and «Fecha» for what they are in a purchase in installments, and
        shows what the installments come to."""
        fields = self.installment_fields
        in_installments = self.mode_input.index() == EXPENSE_MODE and fields.in_installments
        fields.amount_mode.setVisible(in_installments)
        amount_label = _("Monto")
        if in_installments:
            amount_label = _("Cuota") if fields.is_per_installment else _("Total")
        elif self.is_transfer_mode:
            amount_label = _("Sale")
        self.form.labelForField(self.amount_row).setText(amount_label)
        self.form.labelForField(self.date_input).setText(
            _(FIRST_INSTALLMENT_LABEL) if in_installments else _("Fecha")
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
            self.rate_hint.setText(_("Cotización implícita: {rate}").format(rate=text))
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
            (self.account_input, _(CHOOSE_ACCOUNT)),
            (self.to_account_input, _("Elige la cuenta de destino.")),
            (fields.other_input if fields.is_other else fields.count_input, ask_count()),
            (self.amount_input, _(TYPE_AMOUNT)),
            (self.amount_in_input, _("Escribe el monto que entra.")),
            (self.category_input, _(CHOOSE_CATEGORY)),
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
        creates_tags = self._services.tags.any_new(draft.tag_names)
        plan = (
            self.installment_fields.plan_for(draft.amount, draft.occurred_on)
            if draft.type is TransactionType.EXPENSE
            else None
        )
        transaction_id = self._transaction.id if self._transaction else None
        excess = self._services.refunds.excess(draft, transaction_id)
        if excess is not None:
            extra = RefundExtraDialog(self._services, draft, excess, transaction_id, self)
            if not extra.exec():
                # Not split: the refund goes over, and the form says by how much.
                self._services.transactions.validated(draft, transaction_id)
        else:
            self._services.installments.save(draft, plan, self._transaction)
        if not self._transaction:
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
            self._services.transfers.update(self._transaction.transfer_id, draft)
        else:
            self._services.transfers.create(draft)
            self._services.settings.set_last_account_id(source.id)


def _currencies_differ(first: Account | None, second: Account | None) -> bool:
    return bool(first and second and first.currency is not second.currency)
