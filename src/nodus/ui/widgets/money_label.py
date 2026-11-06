"""Labels that show an amount colored by its sign, optionally counting to new values."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget

from nodus.models.money import Money
from nodus.ui.widgets import chart_base
from nodus.ui.widgets.style import set_style_property


class MoneyLabel(QLabel):
    """Shows a ``Money`` in Argentine format, red when negative.

    With ``highlight_positive`` positive amounts turn green too, which suits income and
    expense lists; balances leave them in the normal text color.
    """

    def __init__(
        self, money: Money | None = None, highlight_positive: bool = False, parent: QWidget = None
    ) -> None:
        super().__init__(parent)
        self._highlight_positive = highlight_positive
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if money is not None:
            self.set_money(money)

    def set_money(self, money: Money) -> None:
        self.setText(money.format())
        set_style_property(self, "tone", self._tone(money))

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
            self.setToolTip(money.format())
            self.updateGeometry()
        if self._animation:
            self._animation.stop()
        if (
            previous is None
            or previous.currency is not money.currency
            or previous == money
            or chart_base.DURATION_MS <= 0
        ):
            self._show(money)
            return
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(float(previous.cents))
        self._animation.setEndValue(float(money.cents))
        self._animation.setDuration(chart_base.DURATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(
            lambda cents: self._show(Money(round(cents), money.currency))
        )
        self._animation.finished.connect(lambda: self._show(money))
        self._animation.start()

    def _show(self, money: Money) -> None:
        self._shown = money
        text = money.format()
        if self._compact_when_narrow and not self._fits(text):
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
