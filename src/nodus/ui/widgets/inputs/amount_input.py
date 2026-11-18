"""Text field for amounts typed in Argentine format, read by ``parse_amount``."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from nodus.models.amount_parsing import AmountTextError, parse_amount
from nodus.models.currency import Currency
from nodus.models.language_format import format_decimal
from nodus.models.money import Money
from nodus.ui.widgets.inputs.input_error import InputError


class AmountInput(QWidget):
    """An amount field with the currency symbol in front, e.g. "US$ [ 1.234,56 ]"."""

    def __init__(self, currency: Currency, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._symbol = QLabel()
        self._symbol.setObjectName("AmountSymbol")
        self.line_edit = QLineEdit()
        layout.addWidget(self._symbol)
        layout.addWidget(self.line_edit, stretch=1)
        self._zero_hint = ""
        self.set_currency(currency)

    def set_currency(self, currency: Currency) -> None:
        self._currency = currency
        self._symbol.setText(currency.symbol)
        # Only the default hint ("0,00", or "0" for a currency without cents) follows the
        # currency; a field may set one of its own.
        if self.line_edit.placeholderText() in {"", self._zero_hint}:
            self._zero_hint = format_decimal(0, currency.decimals)
            self.line_edit.setPlaceholderText(self._zero_hint)

    def money(self) -> Money:
        """The typed amount; an empty field counts as zero. Raises ``InputError`` about
        this field when the text is not an amount."""
        text = self.line_edit.text()
        if not text.strip():
            return Money.zero(self._currency)
        try:
            return parse_amount(text, self._currency)
        except AmountTextError as error:
            raise InputError(str(error), self) from error  # user-text: parse_amount's own

    def set_money(self, money: Money) -> None:
        self.set_currency(money.currency)
        self.line_edit.setText(money.format_number())
