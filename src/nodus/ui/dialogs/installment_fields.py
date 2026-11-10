"""The «Cuotas» row of the expense form: how many, picked from the usual counts or typed."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from nodus.models.installment_plan import MAX_INSTALLMENTS, MIN_INSTALLMENTS, InstallmentPlan
from nodus.models.money import Money
from nodus.services.errors import ValidationError
from nodus.ui.formatting import format_date
from nodus.ui.theme.design import Space
from nodus.ui.widgets.combo_box import ComboBox
from nodus.ui.widgets.segmented import SegmentedControl

TOTAL, PER_INSTALLMENT = range(2)
AMOUNT_MODES = ["Total", "Por cuota"]
# What card purchases are usually paid in; any other count is typed after «Otra cantidad».
COMMON_COUNTS = (1, 3, 6, 9, 12, 18)
OTHER_COUNT = "Otra cantidad…"


class InstallmentFields(QWidget):
    """«[6 cuotas ▾]», or «[Otra cantidad… ▾] [10]» for a count the list does not offer.

    It comes before the amount, so the list stays short and plain; what the installments
    come to is said once, under the amount (``hint_text``). ``amount_mode`` («Total |
    Por cuota») says how to read that amount, so the form places it next to it; turning
    it never rewrites the number typed, so going back and forth cannot drift by a cent.
    Splits and days come from ``InstallmentPlan``.
    """

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.count_input = ComboBox()
        self.count_input.setAccessibleName("Cuotas")
        self.count_input.setToolTip("En cuántas cuotas se paga")
        for count in COMMON_COUNTS:
            self.count_input.addItem(count_text(count), count)
        self.count_input.insertSeparator(self.count_input.count())
        self.count_input.addItem(OTHER_COUNT, None)
        self.other_input = QLineEdit()
        self.other_input.setPlaceholderText("Cuántas")
        self.other_input.setAccessibleName("Otra cantidad de cuotas")
        self.other_input.setValidator(QIntValidator(1, MAX_INSTALLMENTS, self.other_input))
        self.other_input.hide()
        self.amount_mode = SegmentedControl(AMOUNT_MODES)
        self.amount_mode.setToolTip("El monto es el total de la compra o lo que vale cada cuota")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        layout.addWidget(self.count_input, stretch=1)
        layout.addWidget(self.other_input, stretch=1)

        self.count_input.currentIndexChanged.connect(self._count_picked)
        self.other_input.textChanged.connect(self._changed)
        self.amount_mode.changed.connect(self._changed)

    @property
    def is_other(self) -> bool:
        return self.count_input.currentData() is None

    @property
    def count(self) -> int | None:
        """How many installments; None while «Otra cantidad» has no number from 1 to 72."""
        if not self.is_other:
            return self.count_input.currentData()
        text = self.other_input.text()
        count = int(text) if text.isdigit() else 0
        return count if 1 <= count <= MAX_INSTALLMENTS else None

    @property
    def in_installments(self) -> bool:
        """More than one installment, or another count still being typed."""
        return self.count != 1

    @property
    def is_per_installment(self) -> bool:
        return self.amount_mode.index() == PER_INSTALLMENT

    def set_count(self, count: int) -> None:
        """Picks ``count`` in the list, or types it after «Otra cantidad»."""
        index = self.count_input.findData(count)
        if index >= 0:
            self.count_input.setCurrentIndex(index)
            return
        self.other_input.setText(str(count))
        self.count_input.setCurrentIndex(self.count_input.findText(OTHER_COUNT))

    def set_plan(self, plan: InstallmentPlan) -> None:
        """Shows a saved purchase: its count, with the amount read as the total."""
        self.amount_mode.set_index(TOTAL)
        self.set_count(plan.count)

    def plan_for(self, amount: Money, first_due_on: date) -> InstallmentPlan | None:
        """The plan for ``amount`` read as this row says; None for a single payment."""
        count = self.count
        if count is None:
            raise ValidationError(
                f"Escribe en cuántas cuotas, de {MIN_INSTALLMENTS} a {MAX_INSTALLMENTS}."
            )
        if count == 1:
            return None
        try:
            if self.is_per_installment:
                return InstallmentPlan.from_installment_amount(amount, count, first_due_on)
            return InstallmentPlan(None, count, amount, first_due_on)
        except ValueError as error:
            raise ValidationError(
                f"El monto no alcanza para {count} cuotas de al menos un centavo."
            ) from error

    def hint_text(self, amount: Money | None, first_due_on: date) -> str | None:
        """What the installments come to, for under the amount: «6 cuotas de $ 12.500,00 ·
        la última, el 10/04/2027», or the total when the amount is per installment. None
        for a single payment, or while the amount or the count is missing or too small."""
        if amount is None or amount.cents <= 0 or not self.in_installments:
            return None
        try:
            plan = self.plan_for(amount, first_due_on)
        except ValidationError:
            return None
        assert plan is not None
        return _hint_text(plan, self.is_per_installment)

    def _count_picked(self) -> None:
        self.other_input.setVisible(self.is_other)
        if self.is_other:
            self.other_input.setFocus()
        self._changed()

    def _changed(self, *_args: object) -> None:
        self.changed.emit()


def count_text(count: int) -> str:
    return "1 pago" if count == 1 else f"{count} cuotas"


def _hint_text(plan: InstallmentPlan, per_installment: bool) -> str:
    last = f"la última, el {format_date(plan.due_dates()[-1])}"
    if per_installment:
        return f"Total {plan.total.format()} · {last}"
    amounts = plan.amounts()
    what = f"{plan.count} cuotas de {amounts[-1].format()}"
    if amounts[0] != amounts[-1]:
        what += f" (la primera, {amounts[0].format()})"
    return f"{what} · {last}"
