"""Text field for amounts typed in Argentine format."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.services.errors import ValidationError

_ALLOWED = re.compile(r"^-?[\d.,]+$")


# The hint of an empty field: "0,00", or "0" for a currency without cents.
_ZERO_HINTS = {True: "0,00", False: "0"}


def parse_amount(text: str) -> Decimal:
    """Reads a number as people type it in Argentina.

    The comma is the decimal separator and the dot groups thousands ("1.234,56"). Since
    many people also type "12.50", a lone dot followed by one or two digits is read as a
    decimal point. Raises ``ValidationError`` when the text is not a number.
    """
    cleaned = text.strip().replace(" ", "")
    if not _ALLOWED.match(cleaned):
        raise ValidationError(f"«{text.strip()}» no es un monto válido.")
    if "," in cleaned:
        normalized = cleaned.replace(".", "").replace(",", ".")
    elif re.search(r"^-?\d*\.\d{1,2}$", cleaned):
        normalized = cleaned
    else:
        normalized = cleaned.replace(".", "")
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ValidationError(f"«{text.strip()}» no es un monto válido.") from error


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
        self.set_currency(currency)

    def set_currency(self, currency: Currency) -> None:
        self._currency = currency
        self._symbol.setText(currency.symbol)
        # Only the default hint follows the currency; a field may set one of its own.
        if self.line_edit.placeholderText() in {"", *_ZERO_HINTS.values()}:
            self.line_edit.setPlaceholderText(_ZERO_HINTS[currency.decimals > 0])

    def money(self) -> Money:
        """The typed amount; an empty field counts as zero."""
        text = self.line_edit.text()
        amount = parse_amount(text) if text.strip() else Decimal(0)
        if not self._currency.decimals and amount != amount.to_integral_value():
            raise ValidationError("Los pesos chilenos no llevan centavos.")
        return Money.from_decimal(amount, self._currency)

    def set_money(self, money: Money) -> None:
        self.set_currency(money.currency)
        self.line_edit.setText(money.format_number())
