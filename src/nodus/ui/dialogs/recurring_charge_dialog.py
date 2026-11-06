"""Dialogs to set up a recurring charge and to pay it."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QWidget

from nodus.models.currency import Currency
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

        self.form.addRow("Nombre", self.name_input)
        self.form.addRow("Monto", self.amount_input)
        self.form.addRow("Cuenta", self.account_input)
        self.form.addRow("Categoría", self.category_input)
        self.form.addRow("Frecuencia", self.frequency_input)
        self.form.addRow("Próximo cobro", self.due_input)
        self.form.addRow("Nota", self.note_input)

        if charge:
            self._load(charge)
        else:
            self.account_input.select(services.settings.last_account_id())

    def _load(self, charge: RecurringCharge) -> None:
        self.name_input.setText(charge.name)
        self.account_input.select(charge.account_id)
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
    in higher than usual."""

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

        self.amount_input = AmountInput(charge.amount.currency)
        self.account_input = account_input_for(services, self.amount_input, [charge.account_id])
        self.account_input.select(charge.account_id)
        self.amount_input.set_money(charge.amount)
        self.date_input = DateInput()
        self.date_input.set_day(today or date.today())
        self.next_hint = QLabel(
            f"Se registra como gasto y el próximo cobro pasa al "
            f"{format_date(charge.following_due())}."
        )
        self.next_hint.setObjectName("FieldHint")
        self.next_hint.setWordWrap(True)

        self.form.addRow("Monto", self.amount_input)
        self.form.addRow("Cuenta", self.account_input)
        self.form.addRow("Fecha", self.date_input)
        self.form.addRow("", self.next_hint)

    def save(self) -> None:
        self._services.recurring.pay(
            self._charge.id,
            self.amount_input.money(),
            self.date_input.day(),
            required_account(self.account_input).id,
        )
        self._event_bus.transactions_changed.emit()
        self._event_bus.recurring_changed.emit()
