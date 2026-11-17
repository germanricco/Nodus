"""Card with the user's net worth: the total, its trend, and how it splits by currency."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.models.currency import TOTAL_CURRENCIES, Currency
from nodus.models.money import Money
from nodus.models.period import Period, format_day_month
from nodus.services.container import Services
from nodus.services.conversion import relative_change
from nodus.services.reports.net_worth_service import NetWorth, NetWorthPoint, trend_change
from nodus.ui.text.formatting import format_date, signed
from nodus.ui.text.labels import HELD_IN_LABELS, NO_RATE_TEXT, rate_text
from nodus.ui.theme.design import ControlSize, Space
from nodus.ui.theme.theme import Theme
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card, card_title
from nodus.ui.widgets.change_badge import ChangeBadge, format_signed_percent
from nodus.ui.widgets.charts.charts import ProportionBar, Segment
from nodus.ui.widgets.charts.line_chart import LineChart, LinePoint, money_formats
from nodus.ui.widgets.color_dot import ColorDot
from nodus.ui.widgets.flow_layout import FlowLayout
from nodus.ui.widgets.inputs.segmented import SegmentedControl
from nodus.ui.widgets.money_label import AnimatedMoneyLabel
from nodus.ui.widgets.style import hint_label, muted_label

# The net worth can be shown in these; the parts held in any currency are listed apart.
CURRENCIES = list(TOTAL_CURRENCIES)
CURRENCY_LABELS = [currency.symbol for currency in CURRENCIES]
# Which chart series each currency takes, so a currency keeps its color everywhere.
SERIES_ORDER = tuple(Currency)
CHANGE_CAPTION = "vs. inicio del período"


def rate_effect_text(effect: Money | None, start: Money | None) -> str:
    """ "+1,2 % por la cotización": the part of a change that comes from the rates, over
    the same starting value as the change; empty when there is none to tell."""
    if effect is None or start is None or effect.is_zero:
        return ""
    change = relative_change(start + effect, start)
    return "" if change is None else f"{format_signed_percent(change)} por la cotización"


def share_text(share: float | None) -> str:
    """A currency's rounded share of the net worth; empty without one."""
    return "" if share is None else f"{round(100 * share)} %"


class CurrencyLegend(QWidget):
    """ "● En pesos  $ 1.236.578,85  47 %": one part of the net worth."""

    def __init__(self, currency: Currency) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        self.dot = ColorDot(size=ControlSize.DOT_SMALL)
        name = muted_label(HELD_IN_LABELS[currency])
        self.amount = AnimatedMoneyLabel()
        self.amount.setObjectName("RowTitle")
        self.share = muted_label("")
        for widget in (self.dot, name, self.amount, self.share):
            layout.addWidget(widget)


class NetWorthCard(Card):
    """The net worth in the currency the user picks, how it moved along the period, and
    what part is held in each currency, with the rates used.

    The dashboard shows it in full, with the trend; the accounts page uses ``compact``,
    which leaves out the chart and the change. Without an exchange rate needed to add the
    currencies up, it shows each subtotal instead of inventing a total.
    """

    rate_requested = Signal()
    # The user chose another currency for the total, which every total that converts
    # currencies follows (EventBus.net_worth_currency_changed).
    currency_changed = Signal()

    def __init__(
        self, services: Services, theme_manager: ThemeManager, compact: bool = False
    ) -> None:
        super().__init__()
        self._services = services
        self._theme = theme_manager.theme
        self._compact = compact
        self._shown: tuple[date, Period | None] | None = None
        self._daily = True
        self._hidden = False
        self._build_header()
        self._build_total()
        self._build_missing_rate()
        self.chart: LineChart | None = None
        if not compact:
            self.chart = LineChart(
                self._theme,
                *money_formats(self.currency, lambda: self._hidden, lambda: self._daily),
            )
            self.body.addWidget(self.chart, stretch=1)
        self.composition = ProportionBar(self._theme)
        self.body.addSpacing(Space.XS)
        self.body.addWidget(self.composition)
        self._build_legend()
        theme_manager.theme_changed.connect(self._set_theme)

    # Layout

    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(Space.M)
        title = card_title("Patrimonio neto")
        self.currency_input = SegmentedControl(CURRENCY_LABELS)
        self.currency_input.setToolTip("Ver el patrimonio neto en pesos o en dólares")
        self.currency_input.set_index(
            CURRENCIES.index(self._services.settings.net_worth_currency())
        )
        self.currency_input.changed.connect(self._set_currency)
        header.addWidget(title)
        header.addWidget(self.currency_input)
        header.addStretch()
        self.change_badge = ChangeBadge()
        self.change_caption = hint_label(CHANGE_CAPTION)
        change = QVBoxLayout()
        change.setSpacing(Space.XXS)
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
        # Only past days are named, beside the amount; today's net worth needs no caption.
        self.day_label = muted_label("")
        row = QHBoxLayout()
        row.setSpacing(Space.S)
        row.addWidget(self.total_label)
        row.addWidget(self.day_label, alignment=Qt.AlignmentFlag.AlignBottom)
        row.addStretch()
        self.body.addLayout(row)

    def _build_missing_rate(self) -> None:
        """The subtotals side by side, for when they cannot be added up."""
        self.missing_rate = QWidget()
        # Wraps, like the legend, when there are many currencies to list.
        layout = FlowLayout(self.missing_rate, h_spacing=32, v_spacing=12)
        self.subtotal_labels: dict[Currency, AnimatedMoneyLabel] = {}
        self._subtotal_columns: dict[Currency, QWidget] = {}
        for currency in Currency:
            column_widget = QWidget()
            column = QVBoxLayout(column_widget)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(Space.XXS)
            caption = QLabel(HELD_IN_LABELS[currency].upper())
            caption.setObjectName("StatCaption")
            amount = AnimatedMoneyLabel()
            amount.setObjectName("StatValueLarge")
            amount.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.subtotal_labels[currency] = amount
            self._subtotal_columns[currency] = column_widget
            column.addWidget(caption)
            column.addWidget(amount)
            layout.addWidget(column_widget)
        self.load_rate_button = QPushButton("Cargar cotización")
        self.load_rate_button.setObjectName("SecondaryButton")
        self.load_rate_button.setToolTip("Hace falta para sumar tus cuentas en otras monedas")
        self.load_rate_button.clicked.connect(self.rate_requested)
        layout.addWidget(self.load_rate_button)
        self.body.addWidget(self.missing_rate)

    def _build_legend(self) -> None:
        # Wraps instead of widening the card when many currencies are held.
        legend = FlowLayout(last_to_the_right=True)
        self.legends = {currency: CurrencyLegend(currency) for currency in Currency}
        for item in self.legends.values():
            legend.addWidget(item)
        self.rate_label = hint_label()
        legend.addWidget(self.rate_label)
        self.body.addLayout(legend)

    # Data

    def currency(self) -> Currency:
        return CURRENCIES[self.currency_input.index()]

    def set_amounts_hidden(self, hidden: bool) -> None:
        """Masks every figure, the chart's included; the shares and the change in percent
        stay, since they tell nothing about how much there is."""
        self._hidden = hidden
        amounts = [self.total_label, *self.subtotal_labels.values()]
        amounts += [legend.amount for legend in self.legends.values()]
        for label in amounts:
            label.set_hidden(hidden)
        if self._shown:
            self.show_day(*self._shown)

    def show_day(self, day: date, period: Period | None = None) -> None:
        """The net worth at the end of ``day``; with ``period``, also its trend along it."""
        self._shown = (day, period)
        currency = self.currency()
        net_worth = self._services.net_worth.net_worth(day)
        total = net_worth.total_in[currency]
        has_total = total is not None
        for widget in (self.total_label, self.composition):
            widget.setVisible(has_total)
        self.day_label.setVisible(has_total and day != date.today())
        self.missing_rate.setVisible(not has_total)
        if total is not None:
            self.total_label.set_money(total)
            self.day_label.setText(f"al {format_date(day)}")
        else:
            for held, label in self.subtotal_labels.items():
                amount = net_worth.by_currency.get(held)
                self._subtotal_columns[held].setVisible(amount is not None)
                if amount is not None:
                    label.set_money(amount)
        self._show_composition(net_worth, currency, day)
        self._show_rates(net_worth, day)
        if self.chart is not None:
            history = self._services.net_worth.history(period, date.today()) if period else []
            opening_day = period.start - timedelta(days=1) if period else None
            opening = self._services.net_worth.net_worth(opening_day) if opening_day else None
            self._show_trend(history, opening, opening_day, currency, has_total)

    def _show_composition(self, net_worth: NetWorth, currency: Currency, day: date) -> None:
        composition = self._services.net_worth.composition(net_worth, currency, day)
        colors = self._colors()
        segments = []
        for held, legend in self.legends.items():
            amount = net_worth.by_currency.get(held)
            legend.setVisible(amount is not None and (not amount.is_zero or held is currency))
            if amount is None:
                continue
            legend.dot.set_color(colors[held])
            legend.amount.set_money(amount)
            part = composition.parts[held]
            legend.share.setText(share_text(composition.share(held)))
            segments.append(Segment(colors[held], max(0, part.cents) if part else 0, held.value))
        self.composition.set_segments(segments)

    def _show_rates(self, net_worth: NetWorth, day: date) -> None:
        """The rate of the dollar, which the totals always need, and of any other foreign
        currency held."""
        texts = []
        for held, amount in net_worth.by_currency.items():
            if not held.is_foreign or (held is not Currency.USD and amount.is_zero):
                continue
            rate = self._services.exchange_rates.rate_on(day, held)
            if rate is not None:
                texts.append(
                    f"{rate_text(held, rate.quote, rate.rate)} · {format_day_month(rate.rate_date)}"
                )
            elif held is Currency.USD:
                texts.append(NO_RATE_TEXT)
            else:
                texts.append(f"{held.symbol} {NO_RATE_TEXT.lower()}")
        self.rate_label.setText("    ".join(texts))

    def _show_trend(
        self,
        history: list[NetWorthPoint],
        opening: NetWorth | None,
        opening_day: date | None,
        currency: Currency,
        has_total: bool,
    ) -> None:
        """The chart along the period, and the change from the opening balance (the end of
        the day before it starts) to its last point. Without a rate for that day, the
        change is measured from the first point that has one."""
        assert self.chart is not None
        self.chart.setVisible(has_total)
        # Month-end points are labelled by month, daily ones by day.
        self._daily = len(history) < 2 or (history[1].day - history[0].day).days == 1
        points = []
        for point in history:
            value = point.net_worth.total_in[currency]
            points.append(LinePoint(point.day, None if value is None else value.cents))
        self.chart.set_points(points)
        change = trend_change(history, opening, opening_day, currency) if has_total else None
        if change is not None:
            difference = change.difference
            self.change_badge.set_change(
                change.change,
                "" if difference.is_zero or self._hidden else signed(difference),
            )
            self._show_rate_effect(change.end, change.start_day, change.first, currency)
            self.change_caption.show()
        else:
            self.change_badge.set_change(None)
            self.change_caption.hide()

    def _show_rate_effect(
        self, end: NetWorthPoint, start_day: date, first: Money, currency: Currency
    ) -> None:
        """Adds to the caption how much of the change comes from the rates, so the same
        period reads differently in pesos and in dollars for a reason the card tells. A
        percent, which says nothing of how much there is, so it stays with hidden amounts."""
        effect = self._services.net_worth.rate_effect(end, start_day, currency)
        text = rate_effect_text(effect, first)
        self.change_caption.setText(f"{CHANGE_CAPTION} · {text}" if text else CHANGE_CAPTION)
        tip = self._rates_moved_tip(end, start_day, currency) if text else ""
        self.change_caption.setToolTip(tip)

    def _rates_moved_tip(self, end: NetWorthPoint, start_day: date, currency: Currency) -> str:
        """ "US$ 1 = $ 1.600,00 → $ 1.580,00" for each rate the total went through that
        moved (those of the foreign currencies held, and of ``currency`` when it is one),
        and that the rest of the change is the user's own."""
        rate_on = self._services.exchange_rates.rate_on
        held = {c for c, amount in end.net_worth.by_currency.items() if not amount.is_zero}
        lines = []
        for foreign in (c for c in Currency if c.is_foreign and (c in held or c is currency)):
            before, after = rate_on(start_day, foreign), rate_on(end.day, foreign)
            if before and after and before.rate != after.rate:
                start_text = rate_text(foreign, before.quote, before.rate)
                end_text = Money.from_decimal(after.rate, after.quote).format()
                lines.append(f"{start_text} → {end_text}")
        lines.append("El resto de la variación es por tus movimientos.")
        return "\n".join(lines)

    # Chart formatting

    # Reactions

    def _set_currency(self, index: int) -> None:
        self._services.settings.set_net_worth_currency(CURRENCIES[index])
        if self._shown:
            self.show_day(*self._shown)
        self.currency_changed.emit()

    def _colors(self) -> dict[Currency, str]:
        return dict(zip(SERIES_ORDER, self._theme.series(), strict=True))

    def _set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.composition.set_theme(theme)
        if self.chart is not None:
            self.chart.set_theme(theme)
        if self._shown:
            self.show_day(*self._shown)
