"""The General card of Ajustes: theme, opening with Windows and motion."""

from __future__ import annotations

from nodus.i18n import N_, Language, _, current_language
from nodus.services.container import Services
from nodus.ui.dialogs.confirm import ask
from nodus.ui.restart import restart
from nodus.ui.theme.design import set_reduced_motion
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.card import Card
from nodus.ui.widgets.inputs.segmented import SegmentedControl
from nodus.ui.widgets.inputs.toggle_switch import ToggleSwitch
from nodus.ui.widgets.setting_row import SettingRow

# Segment order of the theme selector.
THEME_MODES = [ThemeMode.LIGHT, ThemeMode.DARK, ThemeMode.SYSTEM]
THEME_LABELS = [N_("Claro"), N_("Oscuro"), N_("Según el sistema")]

LANGUAGES = list(Language)


class GeneralCard(Card):
    """The preferences of how Nodus looks and opens."""

    def __init__(self, services: Services, theme_manager: ThemeManager) -> None:
        super().__init__(_("General"))
        self._services = services
        self._theme_manager = theme_manager

        # Each language by its own name, so whoever cannot read the current one finds theirs.
        language_row = SettingRow(_("Idioma"), _("Se aplica al reiniciar Nodus."))
        self.language_input = language_row.add(
            SegmentedControl([language.native_name for language in LANGUAGES])
        )
        self.language_input.changed.connect(self._set_language)
        self.body.addWidget(language_row)

        theme_row = SettingRow(
            _("Tema"), _("«Según el sistema» sigue el modo claro u oscuro de Windows.")
        )
        self.theme_input = theme_row.add(SegmentedControl([_(label) for label in THEME_LABELS]))
        self.theme_input.changed.connect(self._set_theme)
        self.body.addWidget(theme_row)

        startup = services.startup
        startup_row = SettingRow(
            _("Abrir Nodus al iniciar Windows"),
            _("Te espera abierto al encender la computadora.")
            if startup.is_available()
            else _("Disponible en la versión instalada."),
        )
        self.startup_input = startup_row.add(ToggleSwitch())
        self.startup_input.setEnabled(startup.is_available())
        if not startup.is_available():
            self.startup_input.setToolTip(_("Disponible en la versión instalada"))
        self.startup_input.clicked.connect(startup.set_enabled)
        self.body.addWidget(startup_row)

        motion_row = SettingRow(
            _("Reducir animaciones"),
            _("Los gráficos y las cifras cambian de una vez, sin moverse."),
        )
        self.reduce_motion_input = motion_row.add(ToggleSwitch())
        self.reduce_motion_input.clicked.connect(self._set_reduce_motion)
        self.body.addWidget(motion_row)

    def refresh(self) -> None:
        chosen = self._services.settings.language() or current_language()
        self.language_input.set_index(LANGUAGES.index(chosen))
        self.theme_input.set_index(THEME_MODES.index(self._theme_manager.mode))
        self.startup_input.setChecked(self._services.startup.is_enabled())
        self.reduce_motion_input.setChecked(self._services.settings.reduce_motion())

    def _set_language(self, index: int) -> None:
        """Saves the language and offers to restart now, since it applies on start."""
        language = LANGUAGES[index]
        if language is (self._services.settings.language() or current_language()):
            return
        self._services.settings.set_language(language)
        if ask(
            self,
            _("Cambiar el idioma"),
            _("Para cambiar el idioma, Nodus se reinicia."),
            _("Reiniciar ahora"),
            _("Más tarde"),
        ):
            restart()

    def _set_reduce_motion(self, reduced: bool) -> None:
        self._services.settings.set_reduce_motion(reduced)
        set_reduced_motion(reduced)

    def _set_theme(self, index: int) -> None:
        mode = THEME_MODES[index]
        if mode is self._theme_manager.mode:
            return
        self._theme_manager.set_mode(mode)
        self._services.settings.set_theme_preference(mode.value)
