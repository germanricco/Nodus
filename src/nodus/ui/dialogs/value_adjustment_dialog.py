"""Dialog to bring a savings or investment account to what it is worth."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from nodus.models.account import Account
from nodus.models.money import Money
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.ui.dialogs.form_dialog import FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.date_input import DateInput
from nodus.ui.widgets.net_worth_card import signed
from nodus.ui.widgets.style import set_style_property


class ValueAdjustmentDialog(FormDialog):
    """Asks for the value the account has, as its app or statement shows it, and saves the
    difference with Nodus's balance as gain or loss, neither income nor expense.

    The last adjustment can be undone from here, for a value typed by mistake.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        account: Account,
        today: date | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"Actualizar valor de «{account.name}»", parent)
        self._services = services
        self._event_bus = event_bus
        self._account = account

        self.date_input = DateInput()
        self.date_input.set_day(today or date.today())
        self.balance_label = QLabel()
        self.value_input = AmountInput(account.currency)
        self.difference_label = QLabel()
        hint = QLabel(
            "Escribe lo que vale hoy, como lo muestra su app o resumen. La diferencia cuenta"
            " como rendimiento: cambia el saldo y el patrimonio neto, no los ingresos ni los"
            " gastos."
        )
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)

        self.form.addRow("Fecha", self.date_input)
        self.form.addRow("Saldo en Nodus", self.balance_label)
        self.form.addRow("Valor actual", self.value_input)
        self.form.addRow("", self.difference_label)
        self.form.addRow("", hint)
        self._add_undo_row()

        self.date_input.dateChanged.connect(self._show_balance)
        self.value_input.line_edit.textChanged.connect(self._show_difference)
        self._show_balance()

    def save(self) -> None:
        self._services.accounts.adjust_value(
            self._account.id, self.value_input.money(), self.date_input.day()
        )
        self._event_bus.accounts_changed.emit()

    def undo_last(self) -> None:
        """Deletes the last adjustment and closes, since the balance went back."""
        self._services.accounts.delete_adjustment(self._last.id)
        self._event_bus.accounts_changed.emit()
        self.accept()

    def _add_undo_row(self) -> None:
        adjustments = self._services.accounts.value_adjustments(self._account.id)
        self._last = adjustments[-1] if adjustments else None
        self.undo_button = QPushButton()
        self.undo_button.setObjectName("SmallButton")
        self.undo_button.clicked.connect(self.undo_last)
        if self._last is not None:
            self.undo_button.setText(
                f"Deshacer el último ({signed(self._last.amount)},"
                f" {format_date(self._last.occurred_on)})"
            )
            self.form.addRow("", self.undo_button)

    def _balance(self) -> Money:
        return self._services.accounts.balance(self._account.id, self.date_input.day())

    def _show_balance(self) -> None:
        balance = self._balance()
        self.balance_label.setText(balance.format())
        if not self.value_input.line_edit.text():
            self.value_input.set_money(balance)
        self._show_difference()

    def _show_difference(self) -> None:
        try:
            difference = self.value_input.money() - self._balance()
        except ValidationError:
            self.difference_label.setText("")
            return
        if difference.is_zero:
            self.difference_label.setText("Sin cambios")
            set_style_property(self.difference_label, "tone", "neutral")
            return
        word = "Ganancia" if not difference.is_negative else "Pérdida"
        self.difference_label.setText(f"{word}: {signed(difference)}")
        set_style_property(
            self.difference_label, "tone", "negative" if difference.is_negative else "positive"
        )
