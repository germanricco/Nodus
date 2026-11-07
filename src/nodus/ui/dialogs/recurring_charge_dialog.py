"""Dialogs to set up a recurring charge and to pay it."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QWidget

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import format_date
from nodus.models.recurring_charge import Frequency, RecurringCharge
from nodus.models.transaction import TransactionType
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.services.recurring_charge_service import RecurringChargeDraft
from nodus.ui.dialogs.account_fields import required_account, selectable_accounts
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import FREQUENCY_LABELS
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.date_input import DateInput
from nodus.ui.widgets.selectors import AccountComboBox, CategoryComboBox


def account_input_for(
    services: Services, amount_input: AmountInput, used_ids: list[int]
) -> AccountComboBox:
    """An account picker whose currency the amount field follows."""
    combo = AccountComboBox()
    combo.set_accounts(selectable_accounts(services, used_ids))

    def follow() -> None:
        account = combo.current_account()
        if account:
            amount_input.set_currency(account.currency)

    combo.currentIndexChanged.connect(follow)
    follow()
    return combo


class RecurringChargeDialog(FormDialog):
    """Sets up a new recurring charge, or edits ``charge`` when given."""

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        charge: RecurringCharge | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Editar cargo" if charge else "Nuevo cargo recurrente", parent)
        self._services = services
        self._event_bus = event_bus
        self._charge = charge

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Por ejemplo, Netflix o Alquiler")
        self.amount_input = AmountInput(Currency.ARS)
        self.account_input = account_input_for(
            services, self.amount_input, [charge.account_id] if charge else []
        )
        self.category_input = CategoryComboBox()
        self.category_input.set_categories(
            [(None, services.categories.category_tree(TransactionType.EXPENSE))]
        )
        self.frequency_input = QComboBox()
        for frequency, label in FREQUENCY_LABELS.items():
            self.frequency_input.addItem(label, frequency)
        self.frequency_input.setCurrentIndex(self.frequency_input.findData(Frequency.MONTHLY))
        self.due_input = DateInput()
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Opcional")
        self.dollars_input = QCheckBox("Se cobra en dólares")
        self.dollars_input.setToolTip(
            "Para una suscripción en dólares que se paga con pesos: al pagarla, anotas los"
            " pesos que salieron"
        )

        self.form.addRow("Nombre", self.name_input)
        self.form.addRow("Monto", self.amount_input)
        self.form.addRow("", self.dollars_input)
        self.form.addRow("Cuenta", self.account_input)
        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("Frecuencia", self.frequency_input)
        self.form.addRow("Próximo cobro", self.due_input)
        self.form.addRow("Nota", self.note_input)

        self.account_input.currentIndexChanged.connect(self._follow_currency)
        self.dollars_input.toggled.connect(self._follow_currency)
        if charge:
            self._load(charge)
        else:
            self.account_input.select(services.settings.last_account_id())
        self._follow_currency()

    def _follow_currency(self) -> None:
        """Only a peso account offers dollars; the amount is in the currency chosen."""
        account = self.account_input.current_account()
        in_pesos = account is not None and account.currency is Currency.ARS
        self.form.setRowVisible(self.dollars_input, in_pesos)
        if in_pesos:
            dollars = self.dollars_input.isChecked()
            self.amount_input.set_currency(Currency.USD if dollars else Currency.ARS)
        elif account is not None:
            self.amount_input.set_currency(account.currency)

    def _load(self, charge: RecurringCharge) -> None:
        self.name_input.setText(charge.name)
        self.account_input.select(charge.account_id)
        account = self.account_input.current_account()
        self.dollars_input.setChecked(
            account is not None and charge.amount.currency is not account.currency
        )
        self.amount_input.set_money(charge.amount)
        self.category_input.select(charge.category_id)
        self.frequency_input.setCurrentIndex(self.frequency_input.findData(charge.frequency))
        self.due_input.set_day(charge.next_due_on)
        self.note_input.setText(charge.note)

    def save(self) -> None:
        category_id = self.category_input.current_id()
        if category_id is None:
            raise ValidationError("Elige una categoría.")
        draft = RecurringChargeDraft(
            name=self.name_input.text(),
            amount=self.amount_input.money(),
            account_id=required_account(self.account_input).id,
            category_id=category_id,
            frequency=self.frequency_input.currentData(),
            next_due_on=self.due_input.day(),
            note=self.note_input.text(),
        )
        if self._charge:
            self._services.recurring.update(self._charge.id, draft)
        else:
            self._services.recurring.create(draft)
        self._event_bus.recurring_changed.emit()


class PayChargeDialog(FormDialog):
    """Records the payment of ``charge``, filled in with what is expected: its amount,
    today's date and its account. The amount can be corrected, as for a bill that came
    in higher than usual.

    A dollar charge paid from a peso account asks for the pesos that came out, filled in
    with the estimate: the rate of the last payment, or the saved one the first time.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        charge: RecurringCharge,
        today: date | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"Pagar {charge.name}", parent)
        self._services = services
        self._event_bus = event_bus
        self._charge = charge
        self.save_button.setText("Registrar pago")

        self._today = today or date.today()
        self.amount_input = AmountInput(charge.amount.currency)
        self.account_input = account_input_for(services, self.amount_input, [charge.account_id])
        self.account_input.select(charge.account_id)
        self.charge_label = QLabel(charge.amount.format())
        self.rate_hint = QLabel()
        self.rate_hint.setObjectName("FieldHint")
        self.rate_hint.setWordWrap(True)
        self.date_input = DateInput()
        self.date_input.set_day(self._today)
        self.next_hint = QLabel(
            f"Se registra como gasto y el próximo cobro pasa al "
            f"{format_date(charge.following_due())}."
        )
        self.next_hint.setObjectName("FieldHint")
        self.next_hint.setWordWrap(True)

        self.form.addRow("Cargo", self.charge_label)
        self.form.addRow("Monto", self.amount_input)
        self.form.addRow("", self.rate_hint)
        self.form.addRow("Cuenta", self.account_input)
        self.form.addRow("Fecha", self.date_input)
        self.form.addRow("", self.next_hint)

        self.account_input.currentIndexChanged.connect(self._fill_amount)
        self._fill_amount()

    def _fill_amount(self) -> None:
        """The charge's amount, or for a payment in another currency the estimate, with
        where it comes from."""
        account = self.account_input.current_account()
        charge = self._charge
        other_currency = account is not None and account.currency is not charge.amount.currency
        self.form.setRowVisible(self.charge_label, other_currency)
        self.form.setRowVisible(self.rate_hint, other_currency)
        self.form.labelForField(self.amount_input).setText(
            "Pesos que salieron" if other_currency else "Monto"
        )
        if not other_currency:
            self.amount_input.set_money(charge.amount)
            return
        estimate = self._services.recurring.estimated_payment(charge, self._today)
        if estimate is None:
            self.amount_input.line_edit.clear()
            self.rate_hint.setText("Sin cotización guardada: escribe los pesos que salieron.")
            return
        self.amount_input.set_money(estimate)
        rate = Money(round(estimate.cents * 100 / charge.amount.cents), estimate.currency)
        source = (
            "como el último pago"
            if charge.last_paid_rate is not None
            else "la cotización guardada; corrígelo con lo que te cobraron"
        )
        self.rate_hint.setText(f"A {rate.format()} por dólar, {source}.")

    def save(self) -> None:
        self._services.recurring.pay(
            self._charge.id,
            self.amount_input.money(),
            self.date_input.day(),
            required_account(self.account_input).id,
        )
        self._event_bus.transactions_changed.emit()
        self._event_bus.recurring_changed.emit()
