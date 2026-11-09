"""Settings section: theme, exchange rates and where the data lives."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodus import __version__
from nodus.links import DONATE_URL, REPOSITORY_URL, feedback_url
from nodus.models.currency import FOREIGN_CURRENCIES, HOME_CURRENCY, Currency
from nodus.models.exchange_rate import ExchangeRate
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.backup_service import BackupService
from nodus.services.container import Services
from nodus.services.errors import BackupError, ValidationError
from nodus.services.rate_feed_service import SOURCES
from nodus.ui.browser import open_url
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.export import export_transactions
from nodus.ui.dialogs.news_dialog import NewsDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.formatting import format_date
from nodus.ui.labels import rate_text
from nodus.ui.pages.page import Page
from nodus.ui.rate_updater import RateUpdater
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.date_input import DateInput
from nodus.ui.widgets.segmented import SegmentedControl
from nodus.ui.widgets.setting_row import SettingRow
from nodus.ui.widgets.style import clear_layout, set_style_property

# Segment order of the theme selector.
THEME_MODES = [ThemeMode.LIGHT, ThemeMode.DARK, ThemeMode.SYSTEM]
THEME_LABELS = ["Claro", "Oscuro", "Según el sistema"]
# Segments of the rate currency selector, one per FOREIGN_CURRENCIES entry.
RATE_CURRENCY_LABELS = ["Dólar", "Euro", "Peso chileno"]
# What the rate form asks for, per currency.
RATE_PLACEHOLDERS = {
    Currency.USD: "Pesos por dólar",
    Currency.EUR: "Pesos por euro",
    Currency.CLP: "Pesos por peso chileno",
}


def open_folder(folder: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def format_rate(rate: ExchangeRate) -> str:
    """ "US$ 1 = $ 1.215,50", how a rate is quoted in Argentina."""
    return rate_text(rate.base, HOME_CURRENCY, rate.rate)


def secondary_button(text: str, on_click: Callable[[], object]) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("SecondaryButton")
    button.clicked.connect(on_click)
    return button


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
        sections.addWidget(self._about_card())
        sections.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.content_layout.addWidget(scroll)

        event_bus.exchange_rates_changed.connect(self.refresh)
        self._rate_updater = RateUpdater(services, event_bus, parent=self)
        self._rate_updater.updated.connect(self._on_rate_updated)
        self._rate_updater.failed.connect(self._on_rate_failed)

    def refresh(self) -> None:
        self.theme_input.set_index(THEME_MODES.index(self._theme_manager.mode))
        self._refresh_rate_currencies()
        self._refresh_rates()
        self._refresh_rate_source()
        self._refresh_backup_status()
        self.check_updates_input.setChecked(self._services.settings.check_updates())
        self.startup_input.setChecked(self._services.startup.is_enabled())

    # General

    def _appearance_card(self) -> Card:
        card = Card("General")
        theme_row = SettingRow("Tema")
        self.theme_input = theme_row.add(SegmentedControl(THEME_LABELS))
        self.theme_input.changed.connect(self._set_theme)
        card.body.addWidget(theme_row)

        startup = self._services.startup
        self.startup_input = QCheckBox("Abrir Nodus al iniciar Windows")
        self.startup_input.setEnabled(startup.is_available())
        if not startup.is_available():
            self.startup_input.setToolTip("Disponible en la versión instalada")
        self.startup_input.clicked.connect(startup.set_enabled)
        card.body.addWidget(self.startup_input)
        return card

    def _set_theme(self, index: int) -> None:
        mode = THEME_MODES[index]
        if mode is self._theme_manager.mode:
            return
        self._theme_manager.set_mode(mode)
        self._services.settings.set_theme_preference(mode.value)

    # Exchange rate

    def _rate_card(self) -> Card:
        card = Card("Cotizaciones")
        self.rate_currency_row = SettingRow("Moneda")
        self.rate_currency_input = self.rate_currency_row.add(
            SegmentedControl(RATE_CURRENCY_LABELS)
        )
        self.rate_currency_input.changed.connect(lambda _index: self._refresh_rates())
        card.body.addWidget(self.rate_currency_row)

        self.rate_source_row = SettingRow("Fuente")
        self.rate_source_input = self.rate_source_row.add(SegmentedControl(list(SOURCES.values())))
        self.rate_source_input.changed.connect(self._set_rate_source)
        self.rate_source_input.setToolTip(
            "Con MEP, Blue u Oficial, Nodus trae el valor de venta del día desde DolarApi"
            " al abrirse; el euro y el peso chileno, con su cotización oficial."
            " Con Manual, las cargas tú."
        )
        self.refresh_rate_button = self.rate_source_row.add(
            secondary_button("Actualizar", self.refresh_rate)
        )
        card.body.addWidget(self.rate_source_row)

        self.current_rate_label = QLabel()
        self.current_rate_label.setObjectName("StatValueLarge")
        self.current_rate_date_label = QLabel()
        set_style_property(self.current_rate_date_label, "muted", True)
        current = QHBoxLayout()
        current.setSpacing(12)
        current.addWidget(self.current_rate_label)
        current.addWidget(self.current_rate_date_label, alignment=Qt.AlignmentFlag.AlignBottom)
        current.addStretch()
        # The euro and the Chilean peso ignore the dollar's source.
        self.official_rate_label = QLabel("Oficial, desde DolarApi")
        set_style_property(self.official_rate_label, "muted", True)
        current.addWidget(self.official_rate_label, alignment=Qt.AlignmentFlag.AlignBottom)
        card.body.addSpacing(4)
        card.body.addLayout(current)
        card.body.addSpacing(4)

        self.rate_date_input = DateInput()
        self.rate_value_input = AmountInput(Currency.ARS)
        self.rate_value_input.setFixedWidth(200)
        self.save_rate_button = QPushButton("Guardar")
        self.save_rate_button.setObjectName("PrimaryButton")
        self.save_rate_button.setToolTip("Si ya hay una cotización para esa fecha, se reemplaza.")
        self.save_rate_button.clicked.connect(self.save_rate)
        self.rate_value_input.line_edit.returnPressed.connect(self.save_rate)
        form = QHBoxLayout()
        form.setSpacing(8)
        form.addWidget(self.rate_date_input)
        self.rate_unit_label = QLabel()
        form.addWidget(self.rate_unit_label)
        form.addWidget(self.rate_value_input)
        form.addWidget(self.save_rate_button)
        form.addStretch()
        card.body.addLayout(form)

        self.rate_error_label = QLabel()
        self.rate_error_label.setObjectName("ErrorLabel")
        self.rate_error_label.hide()
        card.body.addWidget(self.rate_error_label)

        history_title = QLabel("HISTORIAL")
        history_title.setObjectName("CardTitle")
        card.body.addSpacing(8)
        card.body.addWidget(history_title)
        self._history = QVBoxLayout()
        self._history.setSpacing(0)
        card.body.addLayout(self._history)
        return card

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
            self.rate_source_row.set_detail("Consultando…")
            self._rate_updater.update(force=True)

    def _on_rate_updated(self, _rates: dict[Currency, Decimal]) -> None:
        self.rate_source_row.set_detail("Actualizada hoy")

    def _on_rate_failed(self) -> None:
        self.rate_source_row.set_detail("Sin conexión", error=True)

    def _refresh_rate_source(self) -> None:
        feed = self._services.rate_feed
        self.rate_source_input.set_index(list(SOURCES).index(feed.source()))
        automatic = feed.is_automatic()
        self.refresh_rate_button.setVisible(automatic)
        self.rate_source_row.set_detail(
            "Actualizada hoy" if automatic and not feed.due(date.today()) else ""
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
        self.rate_unit_label.setText(f"{currency.symbol} 1 =")
        self.rate_value_input.line_edit.setPlaceholderText(RATE_PLACEHOLDERS[currency])
        self.official_rate_label.setVisible(
            currency is not Currency.USD and self._services.rate_feed.is_automatic()
        )
        current = self._services.exchange_rates.rate_on(today, currency)
        self.current_rate_label.setText(format_rate(current) if current else "Sin cotización")
        self.current_rate_date_label.setText(format_date(current.rate_date) if current else "")
        clear_layout(self._history)
        history = self._services.exchange_rates.history(currency)
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
        data_row = SettingRow("Archivo de datos", str(data_file))
        self.data_path_label = data_row.detail
        self.data_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        data_row.add(secondary_button("Abrir carpeta", lambda: open_folder(data_file.parent)))

        self.backup_row = SettingRow("Copia de seguridad")
        self.backup_row.setToolTip(
            "Nodus guarda una copia por día al abrirse y conserva las últimas"
            f" {BackupService.KEEP}."
        )
        self.backup_now_button = self.backup_row.add(
            secondary_button("Hacer copia", self.backup_now)
        )
        self.backup_row.add(secondary_button("Abrir carpeta", self._open_backups_folder))

        restore_row = SettingRow("Restaurar")
        self.restore_button = restore_row.add(
            secondary_button("Elegir copia…", self.restore_backup)
        )
        export_row = SettingRow("Exportar transacciones")
        self.export_all_button = export_row.add(secondary_button("Exportar CSV", self.export_all))

        for row in (data_row, self.backup_row, restore_row, export_row):
            card.body.addWidget(row)
        return card

    def _refresh_backup_status(self) -> None:
        backups = self._services.backups
        if backups.last_error:
            self.backup_row.set_detail(backups.last_error, error=True)
            return
        last = backups.last_backup()
        self.backup_row.set_detail(f"Última: {format_date(last)}" if last else "Sin copias")

    def backup_now(self) -> None:
        try:
            self._services.backups.create(date.today())
        except BackupError as error:
            QMessageBox.warning(self.window(), "Copia de seguridad", f"No se pudo copiar: {error}")
        self._refresh_backup_status()

    def export_all(self) -> None:
        """Every transaction ever recorded, for a spreadsheet or another app."""
        export_transactions(
            self.window(),
            self._services,
            self._services.transactions.list_transactions(TransactionFilter()),
            f"nodus-transacciones-{date.today():%Y-%m-%d}.csv",
        )

    def _open_backups_folder(self) -> None:
        backups_dir = self._services.backups.backups_dir
        backups_dir.mkdir(parents=True, exist_ok=True)
        open_folder(backups_dir)

    def restore_backup(self) -> None:
        """Replaces the data with a copy the user picks, after confirming."""
        backups_dir = self._services.backups.backups_dir
        path, _filter = QFileDialog.getOpenFileName(
            self.window(), "Restaurar desde una copia", str(backups_dir), "Copias de Nodus (*.db)"
        )
        if not path:
            return
        text = (
            f"Tus datos actuales se van a reemplazar por los de «{Path(path).name}». Antes se"
            " guarda una copia de cómo están ahora, en la carpeta de copias."
        )
        if not confirm(self.window(), "Restaurar copia", text, action="Restaurar"):
            return
        try:
            self._services.backups.restore(Path(path), datetime.now())
        except ValidationError as error:
            QMessageBox.warning(self.window(), "Restaurar copia", str(error))
            return
        self._theme_manager.set_mode(
            ThemeMode.from_setting(self._services.settings.theme_preference())
        )
        self._event_bus.emit_all()
        self.refresh()
        QMessageBox.information(self.window(), "Restaurar copia", "Se restauró la copia.")

    # About

    def show_news(self) -> None:
        NewsDialog.for_entries(self._services.news.all_entries(), parent=self.window()).exec()

    def _about_card(self) -> Card:
        card = Card("Acerca de Nodus")
        version_row = SettingRow(f"Versión {__version__}")
        version_row.add(secondary_button("Ver en GitHub", lambda: open_url(REPOSITORY_URL)))
        card.body.addWidget(version_row)
        news_row = SettingRow("Novedades")
        news_row.add(secondary_button("Ver novedades", self.show_news))
        card.body.addWidget(news_row)
        feedback_row = SettingRow("Comentarios")
        feedback_row.add(secondary_button("Enviar comentarios", lambda: open_url(feedback_url())))
        card.body.addWidget(feedback_row)
        donate_row = SettingRow("Apoyar el proyecto")
        donate_row.add(secondary_button("Invitar un cafecito", lambda: open_url(DONATE_URL)))
        card.body.addWidget(donate_row)
        self.check_updates_input = QCheckBox("Buscar actualizaciones al iniciar")
        self.check_updates_input.setToolTip(
            "Consulta en GitHub cuál es la última versión publicada. No envía ningún dato tuyo."
        )
        self.check_updates_input.clicked.connect(self._services.settings.set_check_updates)
        card.body.addWidget(self.check_updates_input)
        return card
