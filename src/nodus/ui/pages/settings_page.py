"""Settings section: theme, dollar exchange rate and where the data lives."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus.models.currency import Currency
from nodus.models.exchange_rate import ExchangeRate
from nodus.models.money import Money
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.pages.page import Page
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.date_input import DateInput
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.style import clear_layout, set_style_property

# Segment order of the theme selector.
THEME_MODES = [ThemeMode.LIGHT, ThemeMode.DARK, ThemeMode.SYSTEM]
THEME_LABELS = ["Claro", "Oscuro", "Según el sistema"]


def format_rate(rate: ExchangeRate) -> str:
    """ "US$ 1 = $ 1.215,50", how the dollar rate is quoted in Argentina."""
    return f"US$ 1 = {Money.from_decimal(rate.rate, Currency.ARS).format()}"


class RateRow(QWidget):
    """One entry of the rate history, with a button to delete it."""

    delete_requested = Signal(object)  # ExchangeRate

    def __init__(self, rate: ExchangeRate) -> None:
        super().__init__()
        self.rate = rate
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        day = QLabel(format_date(rate.rate_date))
        set_style_property(day, "muted", True)
        day.setMinimumWidth(90)
        layout.addWidget(day)
        layout.addWidget(QLabel(format_rate(rate)), stretch=1)
        self.delete_button = QPushButton("Eliminar")
        self.delete_button.setObjectName("SmallButton")
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(rate))
        layout.addWidget(self.delete_button)


class SettingsPage(Page):
    """Preferences grouped in cards: appearance, exchange rate and data file."""

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__("Ajustes")
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager

        container = QWidget()
        sections = QVBoxLayout(container)
        sections.setContentsMargins(0, 0, 0, 0)
        sections.setSpacing(16)
        sections.addWidget(self._appearance_card())
        sections.addWidget(self._rate_card())
        sections.addWidget(self._data_card())
        sections.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        event_bus.exchange_rates_changed.connect(self.refresh)

    def refresh(self) -> None:
        self.theme_input.set_index(THEME_MODES.index(self._theme_manager.mode))
        self._refresh_rates()

    # Appearance

    def _appearance_card(self) -> Card:
        card = Card("Apariencia")
        self.theme_input = SegmentedControl(THEME_LABELS)
        self.theme_input.changed.connect(self._set_theme)
        row = QHBoxLayout()
        row.addWidget(self.theme_input)
        row.addStretch()
        card.body.addLayout(row)
        return card

    def _set_theme(self, index: int) -> None:
        mode = THEME_MODES[index]
        if mode is self._theme_manager.mode:
            return
        self._theme_manager.set_mode(mode)
        self._services.settings.set_theme_preference(mode.value)

    # Exchange rate

    def _rate_card(self) -> Card:
        card = Card("Cotización del dólar")
        intro = QLabel(
            "Cuántos pesos vale un dólar, según la cotización que uses (MEP, blue, oficial)."
            " Se usa para ver el patrimonio en las dos monedas; cada fecha usa la última"
            " cotización cargada hasta ese día."
        )
        intro.setWordWrap(True)
        set_style_property(intro, "muted", True)
        card.body.addWidget(intro)

        self.current_rate_label = QLabel()
        self.current_rate_label.setObjectName("RowTitle")
        card.body.addWidget(self.current_rate_label)

        self.rate_date_input = DateInput()
        self.rate_value_input = AmountInput(Currency.ARS)
        self.rate_value_input.line_edit.setPlaceholderText("Pesos por dólar")
        self.rate_value_input.setFixedWidth(200)
        self.save_rate_button = QPushButton("Guardar cotización")
        self.save_rate_button.setObjectName("PrimaryButton")
        self.save_rate_button.clicked.connect(self.save_rate)
        self.rate_value_input.line_edit.returnPressed.connect(self.save_rate)
        form = QHBoxLayout()
        form.setSpacing(8)
        form.addWidget(QLabel("Fecha"))
        form.addWidget(self.rate_date_input)
        form.addSpacing(8)
        form.addWidget(QLabel("US$ 1 ="))
        form.addWidget(self.rate_value_input)
        form.addWidget(self.save_rate_button)
        form.addStretch()
        card.body.addLayout(form)

        self.rate_error_label = QLabel()
        self.rate_error_label.setObjectName("ErrorLabel")
        self.rate_error_label.hide()
        card.body.addWidget(self.rate_error_label)
        hint = QLabel("Si ya hay una cotización para esa fecha, se reemplaza.")
        hint.setObjectName("FieldHint")
        card.body.addWidget(hint)

        history_title = QLabel("HISTORIAL")
        history_title.setObjectName("CardTitle")
        card.body.addSpacing(8)
        card.body.addWidget(history_title)
        self._history = QVBoxLayout()
        self._history.setSpacing(0)
        card.body.addLayout(self._history)
        return card

    def save_rate(self) -> None:
        try:
            value = self.rate_value_input.money().to_decimal()
            self._services.exchange_rates.set_rate(self.rate_date_input.day(), value)
        except ValidationError as error:
            self.rate_error_label.setText(str(error))
            self.rate_error_label.show()
            return
        self.rate_value_input.line_edit.clear()
        self._event_bus.exchange_rates_changed.emit()

    def _refresh_rates(self) -> None:
        today = date.today()
        self.rate_error_label.hide()
        self.rate_date_input.set_day(today)
        current = self._services.exchange_rates.rate_on(today)
        self.current_rate_label.setText(
            f"Vigente hoy: {format_rate(current)} (del {format_date(current.rate_date)})"
            if current
            else "Todavía no hay una cotización cargada."
        )
        clear_layout(self._history)
        history = self._services.exchange_rates.history()
        if not history:
            empty = QLabel("Sin cotizaciones.")
            set_style_property(empty, "muted", True)
            self._history.addWidget(empty)
        for rate in history:
            row = RateRow(rate)
            row.delete_requested.connect(self._delete_rate)
            self._history.addWidget(row)

    def _delete_rate(self, rate: ExchangeRate) -> None:
        text = f"Se va a eliminar la cotización del {format_date(rate.rate_date)}."
        if confirm(self.window(), "Eliminar cotización", text):
            self._services.exchange_rates.delete(rate.id)
            self._event_bus.exchange_rates_changed.emit()

    # Data

    def _data_card(self) -> Card:
        card = Card("Tus datos")
        data_file = self._services.settings.data_file
        text = QLabel(
            "Todo lo que cargas en Nodus vive en un único archivo en tu computadora. Para"
            " hacer una copia de seguridad, copia ese archivo con Nodus cerrado."
        )
        text.setWordWrap(True)
        set_style_property(text, "muted", True)
        self.data_path_label = QLabel(str(data_file))
        self.data_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.data_path_label.setWordWrap(True)
        open_button = QPushButton("Abrir carpeta")
        open_button.setObjectName("SecondaryButton")
        open_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_file.parent)))
        )
        row = QHBoxLayout()
        row.addWidget(self.data_path_label, stretch=1)
        row.addWidget(open_button)
        card.body.addWidget(text)
        card.body.addLayout(row)
        return card
