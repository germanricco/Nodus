"""The Acerca de Nodus card of Ajustes: the version, updates, help and the project."""

from __future__ import annotations

from PySide6.QtCore import Signal

from nodus import __version__
from nodus.i18n import _
from nodus.links import DONATE_URL, REPOSITORY_URL, feedback_url
from nodus.services.container import Services
from nodus.ui.browser import open_folder, open_url
from nodus.ui.dialogs.news_dialog import NewsDialog
from nodus.ui.text.labels import TOUR_LABEL
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.inputs.toggle_switch import ToggleSwitch
from nodus.ui.widgets.setting_row import SettingRow
from nodus.ui.widgets.style import secondary_button


class AboutCard(Card):
    """Nodus itself: the version, updates, news, help, the tour, the log and the project."""

    tour_requested = Signal()
    help_requested = Signal()

    def __init__(self, services: Services) -> None:
        super().__init__(_("Acerca de Nodus"))
        self._services = services
        version_row = SettingRow(
            _("Versión {version}").format(version=__version__),
            _("El código fuente, abierto a todos."),
        )
        version_row.add(secondary_button(_("Ver en GitHub"), lambda: open_url(REPOSITORY_URL)))
        updates_row = SettingRow(
            _("Buscar actualizaciones al iniciar"),
            _("Consulta en GitHub cuál es la última versión publicada. No envía ningún dato tuyo."),
        )
        self.check_updates_input = updates_row.add(ToggleSwitch())
        self.check_updates_input.clicked.connect(services.settings.set_check_updates)
        news_row = SettingRow(_("Novedades"), _("Lo que trajo cada versión."))
        news_row.add(secondary_button(_("Ver novedades"), self.show_news))
        tour_row = SettingRow(_("Recorrido guiado"), _("Dónde está cada cosa, en un minuto."))
        tour_row.add(secondary_button(_(TOUR_LABEL), self.tour_requested.emit))
        help_row = SettingRow(_("Ayuda"), _("Cómo se hace cada cosa y los atajos. También con F1."))
        help_row.add(secondary_button(_("Abrir la ayuda"), self.help_requested.emit))
        logs_row = SettingRow(
            _("Registro de errores"),
            _("Lo que anota Nodus para encontrar un error. Queda en tu computadora."),
        )
        self.logs_button = logs_row.add(
            secondary_button(_("Abrir carpeta"), lambda: open_folder(services.settings.logs_folder))
        )
        feedback_row = SettingRow(_("Comentarios"), _("Una idea o un error, sin crear una cuenta."))
        feedback_row.add(
            secondary_button(_("Enviar comentarios"), lambda: open_url(feedback_url()))
        )
        donate_row = SettingRow(
            _("Apoyar el proyecto"), _("Nodus es gratis y lo va a seguir siendo.")
        )
        donate_row.add(secondary_button(_("Invitar un cafecito"), lambda: open_url(DONATE_URL)))
        for row in (
            version_row,
            updates_row,
            news_row,
            help_row,
            tour_row,
            feedback_row,
            logs_row,
            donate_row,
        ):
            self.body.addWidget(row)

    def refresh(self) -> None:
        self.check_updates_input.setChecked(self._services.settings.check_updates())

    def show_news(self) -> None:
        NewsDialog.for_entries(self._services.news.all_entries(), parent=self.window()).exec()
