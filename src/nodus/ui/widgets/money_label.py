"""Labels that show an amount colored by its sign, optionally counting to new values."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QVariantAnimation
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget

from nodus.models.money import Money
from nodus.services.account_group_service import GroupTotal
from nodus.ui.theme.design import Easing, Motion, motion_ms
from nodus.ui.widgets import chart_base
from nodus.ui.widgets.style import set_style_property


def masked(money: Money) -> str:
    """ "$ ••••": only the currency of an amount the user chose to hide."""
    return f"{money.currency.symbol} ••••"


def amount_text(money: Money, hidden: bool) -> str:
    """The amount, or only its currency when the user hides amounts."""
    return masked(money) if hidden else money.format()


def month_change_text(change: Money | None, hidden: bool) -> str:
    """ "+US$ 50,00 este mes", "-US$ 50,00 este mes" or "Sin cambios este mes": short,
    so it fits under a figure in a tile."""
    if change is None:
        return ""
    if change.is_zero:
        return "Sin cambios este mes"
    sign = "-" if change.is_negative else "+"
    size = -change if change.is_negative else change
    return f"{sign}{amount_text(size, hidden)} este mes"


def total_text(total: GroupTotal, hidden: bool) -> tuple[str, str]:
    """A group's subtotal and its tooltip: "≈" when it converts currencies, "—" when a
    rate is missing to add it up."""
    if total.amount is None:
        return "—", "Falta una cotización para sumar las cuentas de este grupo."
    text = masked(total.amount) if hidden else total.amount.format()
    if total.approximate:
        return f"≈ {text}", "Convertido con la cotización del día."
    return text, ""


class MoneyLabel(QLabel):
    """Shows a ``Money`` in Argentine format, red when negative.

    With ``highlight_positive`` positive amounts turn green too, which suits income and
    expense lists; balances leave them in the normal text color. ``set_hidden`` masks the
    figure, for when someone else can see the screen.
    """

    def __init__(
        self, money: Money | None = None, highlight_positive: bool = False, parent: QWidget = None
    ) -> None:
        super().__init__(parent)
        self._highlight_positive = highlight_positive
        self._hidden = False
        self._value: Money | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if money is not None:
            self.set_money(money)

    def set_money(self, money: Money) -> None:
        self._value = money
        self.setText(self._text(money))
        set_style_property(self, "tone", self._tone(money))

    def set_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        if self._value is not None:
            self.set_money(self._value)

    def _text(self, money: Money) -> str:
        return masked(money) if self._hidden else money.format()

    def _tone(self, money: Money) -> str:
        if money.is_negative:
            return "negative"
        if self._highlight_positive and not money.is_zero:
            return "positive"
        return "neutral"


class AnimatedMoneyLabel(MoneyLabel):
    """A ``MoneyLabel`` that counts from the amount it showed to the new one.

    Used for the large dashboard figures, so a new transaction visibly moves them. With
    ``compact_when_narrow`` an amount that doesn't fit is shortened ("$ 8,8 M") and the
    full figure goes to the tooltip; the layout still sizes the label for the full figure,
    so shortening never changes the card's width.
    """

    def __init__(
        self,
        money: Money | None = None,
        highlight_positive: bool = False,
        parent: QWidget = None,
        compact_when_narrow: bool = False,
    ) -> None:
        self._money: Money | None = None
        self._shown: Money | None = None
        self._animation: QVariantAnimation | None = None
        self._compact_when_narrow = compact_when_narrow
        super().__init__(money, highlight_positive, parent)

    def money(self) -> Money | None:
        return self._money

    def set_money(self, money: Money) -> None:
        previous = self._money
        self._money = money
        set_style_property(self, "tone", self._tone(money))
        if self._compact_when_narrow:
            self.setToolTip("" if self._hidden else money.format())
            self.updateGeometry()
        if self._animation:
            self._animation.stop()
        if (
            previous is None
            or previous.currency is not money.currency
            or previous == money
            or motion_ms(Motion.SLOW) <= 0
        ):
            self._show(money)
            return
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(float(previous.cents))
        self._animation.setEndValue(float(money.cents))
        self._animation.setDuration(motion_ms(Motion.SLOW))
        self._animation.setEasingCurve(Easing.SETTLE)
        self._animation.valueChanged.connect(
            lambda cents: self._show(Money(round(cents), money.currency))
        )
        self._animation.finished.connect(lambda: self._show(money))
        self._animation.start()

    def set_hidden(self, hidden: bool) -> None:
        self._hidden = hidden
        if self._money is not None:
            if self._animation:
                self._animation.stop()
            self._shown = None  # shown at once, without counting
            self.set_money(self._money)

    def _show(self, money: Money) -> None:
        self._shown = money
        text = self._text(money)
        if self._compact_when_narrow and not self._hidden and not self._fits(text):
            text = chart_base.format_compact(money.cents, money.currency)
        self.setText(text)

    def _fits(self, text: str) -> bool:
        return self.fontMetrics().horizontalAdvance(text) <= self.contentsRect().width()

    def _full_text_size(self, hint: QSize) -> QSize:
        if self._money is None:
            return hint
        margins = self.contentsMargins()
        width = self.fontMetrics().horizontalAdvance(self._money.format())
        return QSize(width + margins.left() + margins.right() + 2 * self.margin(), hint.height())

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = super().sizeHint()
        return self._full_text_size(hint) if self._compact_when_narrow else hint

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = super().minimumSizeHint()
        return self._full_text_size(hint) if self._compact_when_narrow else hint

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._compact_when_narrow and self._shown is not None:
            self._show(self._shown)
