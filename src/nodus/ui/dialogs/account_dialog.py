"""Dialog to create or edit an account."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.models.account import Account, AccountType
from nodus.models.currency import Currency
from nodus.services.container import Services
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES, FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import ACCOUNT_TYPE_LABELS, CURRENCY_LABELS
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.combo_box import ComboBox


class AccountDialog(FormDialog):
    """Creates an account, or edits ``account`` when given.

    The currency can only be chosen when creating: the service forbids changing it later,
    so the field is locked while editing.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        account: Account | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Editar cuenta" if account else "Nueva cuenta",
            parent,
            SAVE_CHANGES if account else "Agregar cuenta",
        )
        self._services = services
        self._event_bus = event_bus
        self._account = account

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej.: Banco, Efectivo, Dólares")
        self.type_input = ComboBox()
        for account_type, label in ACCOUNT_TYPE_LABELS.items():
            self.type_input.addItem(label, account_type)
        self.currency_input = ComboBox()
        for currency, label in CURRENCY_LABELS.items():
            self.currency_input.addItem(label, currency)
        self.balance_input = AmountInput(Currency.ARS)
        self.currency_input.currentIndexChanged.connect(
            lambda: self.balance_input.set_currency(self.currency_input.currentData())
        )

        self.form.addRow("Nombre", self.name_input)
        self.form.addRow("Tipo", self.type_input)
        self.form.addRow("Moneda", self.currency_input)
        self.form.addRow("Saldo inicial", self.balance_input)

        if account:
            self._load(account)

    def _load(self, account: Account) -> None:
        self.name_input.setText(account.name)
        self.type_input.setCurrentIndex(self.type_input.findData(account.type))
        self.currency_input.setCurrentIndex(self.currency_input.findData(account.currency))
        self.currency_input.setEnabled(False)
        self.balance_input.set_money(account.initial_balance)

    def save(self) -> None:
        name = self.name_input.text()
        account_type: AccountType = self.type_input.currentData()
        initial_balance = self.balance_input.money()
        if self._account:
            self._services.accounts.update(self._account.id, name, account_type, initial_balance)
        else:
            self._services.accounts.create(
                name, account_type, self.currency_input.currentData(), initial_balance
            )
        self._event_bus.accounts_changed.emit()
