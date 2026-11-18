"""The Cotizaciones card of Ajustes: where rates come from, today's, typing one in and
the history."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from nodus.i18n import _
from nodus.models.currency import FOREIGN_CURRENCIES, HOME_CURRENCY, Currency
from nodus.models.exchange_rate import ExchangeRate
from nodus.models.language_format import with_symbol
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.services.external.rate_feed_service import SOURCES
from nodus.ui.dialogs.confirm import delete_with_confirm
from nodus.ui.event_bus import EventBus
from nodus.ui.rate_updater import shared_rate_updater
from nodus.ui.text.formatting import format_date
from nodus.ui.text.labels import NO_RATE_TEXT, rate_text
from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.busy import start_busy, stop_busy
from nodus.ui.widgets.card import Card, card_title
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.inputs.amount_input import AmountInput
from nodus.ui.widgets.inputs.date_input import DateInput
from nodus.ui.widgets.inputs.segmented import SegmentedControl
from nodus.ui.widgets.setting_row import SettingRow
from nodus.ui.widgets.style import clear_layout, muted_label, secondary_button
from nodus.ui.widgets.tables.row_actions import Effect, MoreButton, RowAction, install_row_actions
from nodus.ui.widgets.toast import show_toast


def rate_currency_labels() -> list[str]:
    """Segments of the rate currency selector, one per FOREIGN_CURRENCIES entry."""
    return [c.name_singular.capitalize() for c in FOREIGN_CURRENCIES]


def rate_placeholder(currency: Currency) -> str:
    """What the rate form asks for: "Pesos por dólar"."""
    return _("{home} por {currency}").format(
        home=HOME_CURRENCY.name_plural.capitalize(), currency=currency.name_singular
    )


def format_rate(rate: ExchangeRate) -> str:
    """ "US$ 1 = $ 1.215,50", how a rate is quoted in Argentina."""
    return rate_text(rate.base, HOME_CURRENCY, rate.rate)


class RateRow(QWidget):
    """One entry of the rate history, with its menu to delete it."""

    delete_requested = Signal(object)  # ExchangeRate

    def __init__(self, rate: ExchangeRate) -> None:
        super().__init__()
        self.rate = rate
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.S, Space.XXS, Space.S, Space.XXS)
        day = muted_label(format_date(rate.rate_date))
        day.setMinimumWidth(Layout.DAY_FIELD_MIN_WIDTH)
        layout.addWidget(day)
        layout.addWidget(QLabel(format_rate(rate)), stretch=1)
        self.more_button = MoreButton(self.actions)
        layout.addWidget(self.more_button)
        install_row_actions(self, self.actions)

    def actions(self) -> list[RowAction]:
        return [
            RowAction(
                _("Eliminar"),
                lambda: self.delete_requested.emit(self.rate),
                "trash",
                destructive=True,
                effect=Effect.CONFIRMED,
            )
        ]


class RatesCard(Card):
    """The exchange rates: the source, today's rate, typing one in and the history."""

    def __init__(self, services: Services, event_bus: EventBus) -> None:
        super().__init__(_("Cotizaciones"))
        self._services = services
        self._event_bus = event_bus
        self._add_choices()
        self._add_current_rate()
        self._add_rate_form()

        history_title = card_title(_("Historial"))
        self.body.addSpacing(Space.S)
        self.body.addWidget(history_title)
        self._history = QVBoxLayout()
        self._history.setSpacing(0)
        self.body.addLayout(self._history)

        self._rate_updater = shared_rate_updater(services, event_bus)
        self._rate_updater.updated.connect(self._on_rate_updated)
        self._rate_updater.failed.connect(self._on_rate_failed)

    def _add_choices(self) -> None:
        """Which currency the card shows and where its rates come from."""
        self.rate_currency_row = SettingRow(
            _("Moneda"), _("La cotización que se ve y se carga debajo.")
        )
        self.rate_currency_input = self.rate_currency_row.add(
            SegmentedControl(rate_currency_labels())
        )
        self.rate_currency_input.changed.connect(lambda _index: self._refresh_rates())
        self.body.addWidget(self.rate_currency_row)

        self.rate_source_row = SettingRow(_("Fuente"))
        self.rate_source_input = self.rate_source_row.add(
            SegmentedControl([_(name) for name in SOURCES.values()])
        )
        self.rate_source_input.changed.connect(self._set_rate_source)
        self.rate_source_input.setToolTip(
            _(
                "Con MEP, Blue u Oficial, Nodus trae el valor de venta del día desde DolarApi"
                " al abrirse; el euro y el peso chileno, con su cotización oficial."
                " Con Manual, las cargas tú."
            )
        )
        self.refresh_rate_button = self.rate_source_row.add(
            secondary_button(_("Actualizar"), self.refresh_rate)
        )
        self.body.addWidget(self.rate_source_row)

    def _add_current_rate(self) -> None:
        self.current_rate_label = QLabel()
        self.current_rate_label.setObjectName("StatValueLarge")
        self.current_rate_date_label = muted_label("")
        current = QHBoxLayout()
        current.setSpacing(Space.M)
        current.addWidget(self.current_rate_label)
        current.addWidget(self.current_rate_date_label, alignment=Qt.AlignmentFlag.AlignBottom)
        current.addStretch()
        # The euro and the Chilean peso ignore the dollar's source.
        self.official_rate_label = muted_label(_("Oficial, desde DolarApi"))
        current.addWidget(self.official_rate_label, alignment=Qt.AlignmentFlag.AlignBottom)
        self.body.addSpacing(Space.XS)
        self.body.addLayout(current)
        self.body.addSpacing(Space.XS)

    def _add_rate_form(self) -> None:
        """Typing a rate in, for a day, with its error under it."""
        self.rate_date_input = DateInput()
        self.rate_value_input = AmountInput(HOME_CURRENCY)
        self.rate_value_input.setFixedWidth(Layout.NUMBER_FIELD_WIDTH)
        self.save_rate_button = QPushButton(_("Guardar cotización"))
        self.save_rate_button.setObjectName("PrimaryButton")
        self.save_rate_button.setToolTip(
            _("Si ya hay una cotización para esa fecha, se reemplaza.")
        )
        self.save_rate_button.clicked.connect(self.save_rate)
        self.rate_value_input.line_edit.returnPressed.connect(self.save_rate)
        form = QHBoxLayout()
        form.setSpacing(Space.S)
        form.addWidget(self.rate_date_input)
        self.rate_unit_label = QLabel()
        form.addWidget(self.rate_unit_label)
        form.addWidget(self.rate_value_input)
        form.addWidget(self.save_rate_button)
        form.addStretch()
        self.body.addLayout(form)

        self.rate_error_label = QLabel()
        self.rate_error_label.setObjectName("ErrorLabel")
        self.rate_error_label.hide()
        self.body.addWidget(self.rate_error_label)

    def refresh(self) -> None:
        self._refresh_rate_currencies()
        self._refresh_rates()
        self._refresh_rate_source()

    def _set_rate_source(self, index: int) -> None:
        source = list(SOURCES)[index]
        feed = self._services.rate_feed
        if source == feed.source():
            return
        feed.set_source(source)
        self._refresh_rate_source()
        self._refresh_rates()
        self.refresh_rate()

    def refresh_rate(self) -> None:
        """Replaces today's rate with the one the chosen source publishes now."""
        if self._services.rate_feed.is_automatic():
            self.rate_source_row.set_detail(_("Consultando…"))
            start_busy(self.refresh_rate_button, _("Actualizando…"))
            self._rate_updater.update(force=True)
            if not self._rate_updater.running:  # nothing was asked for
                stop_busy(self.refresh_rate_button)

    def _on_rate_updated(self, rates: dict[Currency, Decimal]) -> None:
        stop_busy(self.refresh_rate_button)
        self.rate_source_row.set_detail(_("Actualizada hoy"))  # the window says it in a toast

    def _on_rate_failed(self) -> None:
        stop_busy(self.refresh_rate_button)
        self.rate_source_row.set_detail(_("Sin conexión"), error=True)

    def _refresh_rate_source(self) -> None:
        feed = self._services.rate_feed
        self.rate_source_input.set_index(list(SOURCES).index(feed.source()))
        automatic = feed.is_automatic()
        self.refresh_rate_button.setVisible(automatic)
        self.rate_source_row.set_detail(
            _("Actualizada hoy") if automatic and not feed.due(date.today()) else ""
        )

    def save_rate(self) -> None:
        try:
            value = self.rate_value_input.money().to_decimal()
            self._services.exchange_rates.set_rate(
                self.rate_date_input.day(), value, self.rate_currency()
            )
        except ValidationError as error:
            self.rate_error_label.setText(str(error))
            self.rate_error_label.show()
            return
        self.rate_value_input.line_edit.clear()
        self._event_bus.exchange_rates_changed.emit()
        show_toast(self, _("Cotización guardada."))

    def rate_currency(self) -> Currency:
        """The currency whose rates the card shows: the dollar, unless the user picked
        another one in use."""
        return FOREIGN_CURRENCIES[self.rate_currency_input.index()]

    def _refresh_rate_currencies(self) -> None:
        """Offers only the currencies in use; with just the dollar, there is no choice."""
        in_use = self._services.rate_feed.currencies()
        for index, currency in enumerate(FOREIGN_CURRENCIES):
            self.rate_currency_input.set_segment_visible(index, currency in in_use)
        if self.rate_currency() not in in_use:
            self.rate_currency_input.set_index(FOREIGN_CURRENCIES.index(Currency.USD))
        self.rate_currency_row.setVisible(len(in_use) > 1)

    def _refresh_rates(self) -> None:
        today = date.today()
        currency = self.rate_currency()
        self.rate_error_label.hide()
        self.rate_date_input.set_day(today)
        self.rate_unit_label.setText(with_symbol(currency.symbol, "1") + " =")
        self.rate_value_input.line_edit.setPlaceholderText(rate_placeholder(currency))
        self.official_rate_label.setVisible(
            currency is not Currency.USD and self._services.rate_feed.is_automatic()
        )
        current = self._services.exchange_rates.rate_on(today, currency)
        self.current_rate_label.setText(format_rate(current) if current else _(NO_RATE_TEXT))
        self.current_rate_date_label.setText(format_date(current.rate_date) if current else "")
        clear_layout(self._history)
        history = self._services.exchange_rates.history(currency)
        if not history:
            self._history.addWidget(self._no_rates_state())
        for rate in history:
            row = RateRow(rate)
            row.delete_requested.connect(self._delete_rate)
            self._history.addWidget(row)

    def _no_rates_state(self) -> EmptyState:
        """No rates yet: fetch them now with an automatic source, or type one in."""
        state = EmptyState(compact=True)
        if self._services.rate_feed.is_automatic():
            state.set_message(_("Sin cotizaciones."), _("Actualizar ahora"), self.refresh_rate)
        else:
            state.set_message(
                _("Sin cotizaciones."), _("Cargar a mano"), self.rate_value_input.line_edit.setFocus
            )
        return state

    def _delete_rate(self, rate: ExchangeRate) -> None:
        text = _("Se va a eliminar la cotización del {date}.").format(
            date=format_date(rate.rate_date)
        )
        delete_with_confirm(
            self.window(),
            _("Eliminar cotización"),
            text,
            lambda: self._services.exchange_rates.delete(rate.id),
            self._event_bus.exchange_rates_changed,
        )
