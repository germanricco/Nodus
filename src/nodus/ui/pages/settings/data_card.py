"""The Tus datos card of Ajustes: the data file, backups, exporting and restoring."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton

from nodus.i18n import _
from nodus.models.transaction_filter import TransactionFilter
from nodus.services.backups.retention import DAILY, MONTHLY, WEEKLY
from nodus.services.container import Services
from nodus.services.errors import BackupError
from nodus.ui.browser import open_folder
from nodus.ui.dialogs.export import all_transactions_filename, export_transactions
from nodus.ui.dialogs.external_backup import save_copy_outside
from nodus.ui.dialogs.restore_copy import restore_copy
from nodus.ui.dialogs.user_error import user_error
from nodus.ui.event_bus import EventBus
from nodus.ui.text.formatting import format_date
from nodus.ui.theme.design import Space
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.busy import busy
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.inputs.toggle_switch import ToggleSwitch
from nodus.ui.widgets.setting_row import SettingRow
from nodus.ui.widgets.style import secondary_button, separator
from nodus.ui.widgets.toast import show_toast


class DataCard(Card):
    """``restored`` fires after a copy replaced the data, so the whole page reads it anew."""

    restored = Signal()

    def __init__(
        self, services: Services, event_bus: EventBus, theme_manager: ThemeManager
    ) -> None:
        super().__init__(_("Tus datos"))
        self._services = services
        self._event_bus = event_bus
        self._theme_manager = theme_manager

        data_file = services.settings.data_file
        data_row = SettingRow(_("Archivo de datos"), str(data_file))
        self.data_path_label = data_row.detail
        self.data_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        data_row.add(secondary_button(_("Abrir carpeta"), lambda: open_folder(data_file.parent)))

        self.backup_row = SettingRow(_("Copia de seguridad"))
        self.backup_row.setToolTip(
            _(
                "Nodus guarda una copia por día al abrirse y conserva las {daily} más"
                " recientes, una por semana de las últimas {weekly} semanas y una por mes"
                " de los últimos {monthly} meses."
            ).format(daily=DAILY, weekly=WEEKLY, monthly=MONTHLY)
        )
        self.backup_now_button = self.backup_row.add(
            secondary_button(_("Hacer copia"), self.backup_now)
        )
        self.backup_row.add(secondary_button(_("Abrir carpeta"), self._open_backups_folder))

        self.outside_row = SettingRow(_("Copia fuera de la PC"))
        self.outside_row.setToolTip(
            _(
                "Las copias diarias quedan en este disco. Una copia en un pendrive, un disco"
                " externo o una carpeta de Drive u OneDrive salva tus datos si la PC se"
                " pierde o se rompe."
            )
        )
        self.save_outside_button = self.outside_row.add(
            secondary_button(_("Guardar copia en…"), self.save_copy_outside)
        )
        reminder_row = SettingRow(
            _("Recordarme a fin de mes"),
            _("Un aviso en la campana si en el mes no guardaste una copia fuera de la PC."),
        )
        self.backup_reminder_input = reminder_row.add(ToggleSwitch())
        self.backup_reminder_input.clicked.connect(self._set_backup_reminder)

        export_row = SettingRow(
            _("Exportar transacciones"), _("Todas, en un archivo CSV para abrir en una planilla.")
        )
        self.export_all_button = export_row.add(
            secondary_button(_("Exportar CSV"), self.export_all)
        )

        for row in (data_row, self.backup_row, self.outside_row, reminder_row, export_row):
            self.body.addWidget(row)

        # Apart from the everyday actions, since it replaces all the data.
        self.body.addSpacing(Space.XS)
        self.body.addWidget(separator())
        restore_row = SettingRow(
            _("Restaurar una copia"),
            _(
                "Reemplaza tus datos actuales por los de una copia. Antes se guarda una copia"
                " de cómo están ahora."
            ),
        )
        self.restore_button = restore_row.add(QPushButton(_("Restaurar copia…")))
        self.restore_button.setObjectName("DangerButton")
        self.restore_button.clicked.connect(self.restore_backup)
        self.body.addWidget(restore_row)

    def refresh(self) -> None:
        """The state of the backups, with the error of the daily one if it failed."""
        backups = self._services.backups
        if backups.last_error:
            self.backup_row.set_detail(backups.last_error, error=True)
            return
        last = backups.last_backup()
        self.backup_row.set_detail(
            _("Última: {date}").format(date=format_date(last)) if last else _("Sin copias")
        )
        outside = backups.last_external_backup()
        self.outside_row.set_detail(
            _("Última: {date}").format(date=format_date(outside))
            if outside
            else _("Nunca. Guárdala en un pendrive, un disco externo o una carpeta de Drive.")
        )
        self.backup_reminder_input.setChecked(self._services.settings.backup_reminder())

    def save_copy_outside(self) -> None:
        save_copy_outside(
            self.window(), self._services, self._event_bus, button=self.save_outside_button
        )

    def _set_backup_reminder(self, enabled: bool) -> None:
        self._services.settings.set_backup_reminder(enabled)
        self._event_bus.backups_changed.emit()

    def backup_now(self) -> None:
        try:
            with busy(self.backup_now_button, _("Guardando…")):
                self._services.backups.create(date.today())
        except BackupError as error:
            user_error(
                self.window(),
                _("Copia de seguridad"),
                _("No se pudo hacer la copia."),
                _(
                    "Revisa que quede lugar en el disco y vuelve a intentarlo. Tus datos"
                    " siguen como estaban."
                ),
                str(error),
            )
        else:
            show_toast(self, _("Copia guardada."))
        self._event_bus.backups_changed.emit()
        self.refresh()

    def export_all(self) -> None:
        """Every transaction ever recorded, for a spreadsheet or another app."""
        export_transactions(
            self.window(),
            self._services,
            self._services.transactions.list_transactions(TransactionFilter()),
            all_transactions_filename(date.today()),
            button=self.export_all_button,
        )

    def _open_backups_folder(self) -> None:
        open_folder(self._services.backups.backups_dir)

    def restore_backup(self) -> None:
        """Replaces the data with a copy the user picks, after confirming."""
        restored = restore_copy(
            self.window(),
            self._services,
            self._event_bus,
            self._theme_manager,
            self._services.backups.backups_dir,
            self.restore_button,
        )
        if restored:
            self.restored.emit()
