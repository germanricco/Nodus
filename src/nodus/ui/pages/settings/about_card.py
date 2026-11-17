"""The Acerca de Nodus card of Ajustes: the version, updates, help and the project."""

from __future__ import annotations

from PySide6.QtCore import Signal

from nodus import __version__
from nodus.links import DONATE_URL, REPOSITORY_URL, feedback_url
from nodus.services.container import Services
from nodus.ui.browser import open_url
from nodus.ui.dialogs.news_dialog import NewsDialog
from nodus.ui.text.labels import TOUR_LABEL
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.inputs.toggle_switch import ToggleSwitch
from nodus.ui.widgets.setting_row import SettingRow
from nodus.ui.widgets.style import secondary_button


class AboutCard(Card):
    """Nodus itself: the version, updates, news, help, the tour and the project."""

    tour_requested = Signal()
    help_requested = Signal()

    def __init__(self, services: Services) -> None:
        super().__init__("Acerca de Nodus")
        self._services = services
        version_row = SettingRow(f"Versión {__version__}", "El código fuente, abierto a todos.")
        version_row.add(secondary_button("Ver en GitHub", lambda: open_url(REPOSITORY_URL)))
        updates_row = SettingRow(
            "Buscar actualizaciones al iniciar",
            "Consulta en GitHub cuál es la última versión publicada. No envía ningún dato tuyo.",
        )
        self.check_updates_input = updates_row.add(ToggleSwitch())
        self.check_updates_input.clicked.connect(services.settings.set_check_updates)
        news_row = SettingRow("Novedades", "Lo que trajo cada versión.")
        news_row.add(secondary_button("Ver novedades", self.show_news))
        tour_row = SettingRow("Recorrido guiado", "Dónde está cada cosa, en un minuto.")
        tour_row.add(secondary_button(TOUR_LABEL, self.tour_requested.emit))
        help_row = SettingRow("Ayuda", "Cómo se hace cada cosa y los atajos. También con F1.")
        help_row.add(secondary_button("Abrir la ayuda", self.help_requested.emit))
        feedback_row = SettingRow("Comentarios", "Una idea o un error, sin crear una cuenta.")
        feedback_row.add(secondary_button("Enviar comentarios", lambda: open_url(feedback_url())))
        donate_row = SettingRow("Apoyar el proyecto", "Nodus es gratis y lo va a seguir siendo.")
        donate_row.add(secondary_button("Invitar un cafecito", lambda: open_url(DONATE_URL)))
        for row in (
            version_row,
            updates_row,
            news_row,
            help_row,
            tour_row,
            feedback_row,
            donate_row,
        ):
            self.body.addWidget(row)

    def refresh(self) -> None:
        self.check_updates_input.setChecked(self._services.settings.check_updates())

    def show_news(self) -> None:
        NewsDialog.for_entries(self._services.news.all_entries(), parent=self.window()).exec()
