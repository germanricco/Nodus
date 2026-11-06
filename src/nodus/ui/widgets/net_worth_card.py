"""Card with the user's net worth: the total, its trend, and how it splits by currency."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.models.currency import Currency
from nodus.models.money import Money
from nodus.models.period import Period
from nodus.services.container import Services
from nodus.services.dashboard_service import relative_change
from nodus.services.net_worth_service import NetWorth, NetWorthPoint
from nodus.ui.formatting import format_date
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.change_badge import ChangeBadge
from nodus.ui.widgets.chart_base import format_compact
from nodus.ui.widgets.charts import ProportionBar, Segment
from nodus.ui.widgets.color import ColorDot
from nodus.ui.widgets.line_chart import LineChart, LinePoint
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.style import set_style_property

CURRENCIES = [Currency.ARS, Currency.USD]
CURRENCY_LABELS = ["$", "US$"]
HELD_IN = {Currency.ARS: "En pesos", Currency.USD: "En dólares"}


def signed(money: Money) -> str:
    """ "+$ 118.400,00" or "-$ 2.000,00": a change always shows its sign."""
    return money.format() if money.is_negative else f"+{money.format()}"


def share(part: Money, whole: Money) -> str:
    """Rounded percentage of ``whole``; empty when there is no positive whole."""
    if whole.cents <= 0:
        return ""
    return f"{round(100 * max(0, part.cents) / whole.cents)} %"


class CurrencyLegend(QWidget):
    """ "● En pesos  $ 1.236.578,85  47 %": one part of the net worth."""

    def __init__(self, currency: Currency) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.dot = ColorDot("#000000", size=10)
        name = QLabel(HELD_IN[currency])
        set_style_property(name, "muted", True)
        self.amount = AnimatedMoneyLabel()
        self.amount.setObjectName("RowTitle")
        self.share = QLabel()
        set_style_property(self.share, "muted", True)
        for widget in (self.dot, name, self.amount, self.share):
            layout.addWidget(widget)


class NetWorthCard(Card):
    """The net worth in the currency the user picks, how it moved along the period, and
    what part is held in pesos and in dollars, with the rate used.

    The dashboard shows it in full, with the trend; the accounts page uses ``compact``,
    which leaves out the chart and the change. Without the exchange rate needed to add
    both currencies, it shows each subtotal instead of inventing a total.
    """

    rate_requested = Signal()

    def __init__(
        self, services: Services, theme_manager: ThemeManager, compact: bool = False
    ) -> None:
        super().__init__()
        self._services = services
        self._theme = theme_manager.theme
        self._compact = compact
        self._shown: tuple[date, Period | None] | None = None
        self._daily = True
        self._build_header()
        self._build_total()
        self._build_missing_rate()
        self.chart: LineChart | None = None
        if not compact:
            self.chart = LineChart(
                self._theme, self._format_value, self._format_axis, self._format_axis_day
            )
            self.body.addWidget(self.chart, stretch=1)
        self.composition = ProportionBar(self._theme)
        self.body.addSpacing(4)
        self.body.addWidget(self.composition)
        self._build_legend()
        theme_manager.theme_changed.connect(self._set_theme)

    # Layout

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(12)
        title = QLabel("PATRIMONIO")
        title.setObjectName("CardTitle")
        self.currency_input = SegmentedControl(CURRENCY_LABELS)
        self.currency_input.setToolTip("Ver el patrimonio en pesos o en dólares")
        self.currency_input.set_index(
            CURRENCIES.index(self._services.settings.net_worth_currency())
        )
        self.currency_input.changed.connect(self._set_currency)
        header.addWidget(title)
        header.addWidget(self.currency_input)
        header.addStretch()
        self.change_badge = ChangeBadge()
        self.change_caption = QLabel("vs. inicio del período")
        self.change_caption.setObjectName("FieldHint")
        change = QVBoxLayout()
        change.setSpacing(2)
        change.addWidget(self.change_badge, alignment=Qt.AlignmentFlag.AlignRight)
        change.addWidget(self.change_caption, alignment=Qt.AlignmentFlag.AlignRight)
        header.addLayout(change)
        self.body.addLayout(header)
        if self._compact:
            self.change_badge.hide()
            self.change_caption.hide()

    def _build_total(self) -> None:
        self.total_label = AnimatedMoneyLabel()
        self.total_label.setObjectName("StatValueHero")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.day_label = QLabel()
        set_style_property(self.day_label, "muted", True)
        self.body.addWidget(self.total_label)
        self.body.addWidget(self.day_label)

    def _build_missing_rate(self) -> None:
        """Both subtotals side by side, for when they cannot be added up."""
        self.missing_rate = QWidget()
        layout = QHBoxLayout(self.missing_rate)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(32)
        self.subtotal_labels: dict[Currency, AnimatedMoneyLabel] = {}
        for currency in CURRENCIES:
            column = QVBoxLayout()
            column.setSpacing(2)
            caption = QLabel(HELD_IN[currency].upper())
            caption.setObjectName("StatCaption")
            amount = AnimatedMoneyLabel()
            amount.setObjectName("StatValueLarge")
            amount.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.subtotal_labels[currency] = amount
            column.addWidget(caption)
            column.addWidget(amount)
            layout.addLayout(column)
        self.load_rate_button = QPushButton("Cargar cotización")
        self.load_rate_button.setObjectName("SecondaryButton")
        self.load_rate_button.setToolTip("Hace falta para sumar pesos y dólares")
        self.load_rate_button.clicked.connect(self.rate_requested)
        layout.addWidget(self.load_rate_button, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addStretch()
        self.body.addWidget(self.missing_rate)

    def _build_legend(self) -> None:
        legend = QHBoxLayout()
        legend.setSpacing(20)
        self.legends = {currency: CurrencyLegend(currency) for currency in CURRENCIES}
        for item in self.legends.values():
            legend.addWidget(item)
        legend.addStretch()
        self.rate_label = QLabel()
        self.rate_label.setObjectName("FieldHint")
        legend.addWidget(self.rate_label)
        self.body.addLayout(legend)

    # Data

    def currency(self) -> Currency:
        return CURRENCIES[self.currency_input.index()]

    def show_day(self, day: date, period: Period | None = None) -> None:
        """The net worth at the end of ``day``; with ``period``, also its trend along it."""
        self._shown = (day, period)
        currency = self.currency()
        net_worth = self._services.net_worth.net_worth(day)
        total = net_worth.total_in[currency]
        has_total = total is not None
        for widget in (self.total_label, self.day_label, self.composition):
            widget.setVisible(has_total)
        self.missing_rate.setVisible(not has_total)
        if total is not None:
            self.total_label.set_money(total)
            self.day_label.setText("Hoy" if day == date.today() else f"Al {format_date(day)}")
        else:
            for held, label in self.subtotal_labels.items():
                label.set_money(net_worth.by_currency[held])
        self._show_composition(net_worth, currency, day)
        self._show_rate(day)
        if self.chart is not None:
            history = self._services.net_worth.history(period, date.today()) if period else []
            opening = (
                self._services.net_worth.net_worth(period.start - timedelta(days=1))
                if period
                else None
            )
            self._show_trend(history, opening, currency, has_total)

    def _show_composition(self, net_worth: NetWorth, currency: Currency, day: date) -> None:
        parts = {
            held: self._services.exchange_rates.convert(net_worth.by_currency[held], currency, day)
            for held in CURRENCIES
        }
        positive = [p for p in parts.values() if p is not None and p.cents > 0]
        whole = sum(positive[1:], positive[0]) if positive else Money.zero(currency)
        colors = self._colors()
        segments = []
        for held in CURRENCIES:
            legend = self.legends[held]
            legend.dot.set_color(colors[held])
            legend.amount.set_money(net_worth.by_currency[held])
            part = parts[held]
            legend.share.setText(share(part, whole) if part is not None else "")
            legend.setVisible(not net_worth.by_currency[held].is_zero or held is currency)
            segments.append(Segment(colors[held], max(0, part.cents) if part else 0, held.value))
        self.composition.set_segments(segments)

    def _show_rate(self, day: date) -> None:
        rate = self._services.exchange_rates.rate_on(day)
        if rate is None:
            self.rate_label.setText("Sin cotización")
            return
        value = Money.from_decimal(rate.rate, Currency.ARS).format()
        self.rate_label.setText(f"US$ 1 = {value} · {rate.rate_date:%d/%m}")

    def _show_trend(
        self,
        history: list[NetWorthPoint],
        opening: NetWorth | None,
        currency: Currency,
        has_total: bool,
    ) -> None:
        """The chart along the period, and the change from the opening balance (the end of
        the day before it starts) to its last point."""
        assert self.chart is not None
        self.chart.setVisible(has_total)
        # Month-end points are labelled by month, daily ones by day.
        self._daily = len(history) < 2 or (history[1].day - history[0].day).days == 1
        points = []
        for point in history:
            value = point.net_worth.total_in[currency]
            points.append(LinePoint(point.day, None if value is None else value.cents))
        self.chart.set_points(points)
        known = [p.value for p in points if p.value is not None]
        first = opening.total_in[currency] if opening else None
        if has_total and known and first is not None:
            last = Money(int(known[-1]), currency)
            difference = last - first
            self.change_badge.set_change(
                relative_change(last, first), "" if difference.is_zero else signed(difference)
            )
            self.change_caption.show()
        else:
            self.change_badge.set_change(None)
            self.change_caption.hide()

    # Chart formatting

    def _format_value(self, cents: float) -> str:
        return Money(round(cents), self.currency()).format()

    def _format_axis(self, cents: float) -> str:
        return format_compact(cents, self.currency())

    def _format_axis_day(self, day: date) -> str:
        return f"{day:%d/%m}" if self._daily else f"{day:%m/%y}"

    # Reactions

    def _set_currency(self, index: int) -> None:
        self._services.settings.set_net_worth_currency(CURRENCIES[index])
        if self._shown:
            self.show_day(*self._shown)

    def _colors(self) -> dict[Currency, str]:
        return {Currency.ARS: self._theme.accent, Currency.USD: self._theme.income}

    def _set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.composition.set_theme(theme)
        if self.chart is not None:
            self.chart.set_theme(theme)
        if self._shown:
            self.show_day(*self._shown)
