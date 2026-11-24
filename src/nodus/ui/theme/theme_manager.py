"""Applies the light or dark theme to the whole application."""

from __future__ import annotations

import functools
from importlib import resources
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from nodus.ui.theme.design import design_tokens
from nodus.ui.theme.focus import use_keyboard_focus_style
from nodus.ui.theme.theme import DARK, LIGHT, Theme, ThemeMode


@functools.cache
def load_bundled_fonts() -> None:
    """Registers the typeface Nodus brings (``ui/fonts``), ``FONT_FAMILY``. It is loaded
    even if the system has a font of that name, so the screens use the very files they
    were measured with. Once per process: every theme manager calls it."""
    for font in resources.files("nodus.ui.fonts").iterdir():
        if font.name.endswith(".ttf"):
            QFontDatabase.addApplicationFontFromData(font.read_bytes())


class ThemeManager(QObject):
    """Owns the active theme and re-styles the application when it changes.

    In SYSTEM mode it follows the operating system and switches live when the user
    changes the OS setting.
    """

    theme_changed = Signal(object)  # Theme

    def __init__(self, app: QApplication, mode: ThemeMode = ThemeMode.SYSTEM) -> None:
        super().__init__()
        self._app = app
        self._mode = mode
        self._template = Template(
            resources.files("nodus.ui.theme").joinpath("stylesheet.qss").read_text("utf-8")
        )
        # The stylesheet loads images by file path, e.g. the arrow of drop-down fields.
        self._icons_dir = Path(str(resources.files("nodus.ui.icons"))).as_posix()
        load_bundled_fonts()
        # Fusion renders stylesheets the same on every OS, unlike the native Windows style.
        use_keyboard_focus_style(app)
        app.styleHints().colorSchemeChanged.connect(self._on_system_scheme_changed)
        self._theme = self._resolve()
        self._apply()

    @property
    def theme(self) -> Theme:
        return self._theme

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    def set_mode(self, mode: ThemeMode) -> None:
        self._mode = mode
        self._update()

    def _on_system_scheme_changed(self) -> None:
        if self._mode is ThemeMode.SYSTEM:
            self._update()

    def _update(self) -> None:
        theme = self._resolve()
        if theme is not self._theme:
            self._theme = theme
            self._apply()
            self.theme_changed.emit(theme)

    def _resolve(self) -> Theme:
        if self._mode is ThemeMode.SYSTEM:
            is_dark = self._app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            return DARK if is_dark else LIGHT
        return DARK if self._mode is ThemeMode.DARK else LIGHT

    def _apply(self) -> None:
        self._app.setPalette(self._palette(self._theme))
        self._app.setStyleSheet(
            self._template.substitute(
                self._theme.tokens(), **design_tokens(), icons=self._icons_dir
            )
        )

    @staticmethod
    def _palette(theme: Theme) -> QPalette:
        """Palette for widgets the stylesheet does not cover (menus, inputs, dialogs)."""
        palette = QPalette()
        roles = {
            QPalette.ColorRole.Window: theme.background,
            QPalette.ColorRole.WindowText: theme.text,
            QPalette.ColorRole.Base: theme.surface,
            QPalette.ColorRole.AlternateBase: theme.hover,
            QPalette.ColorRole.Text: theme.text,
            QPalette.ColorRole.Button: theme.surface,
            QPalette.ColorRole.ButtonText: theme.text,
            QPalette.ColorRole.Highlight: theme.accent,
            QPalette.ColorRole.HighlightedText: theme.on_accent,
            QPalette.ColorRole.PlaceholderText: theme.text_muted,
            QPalette.ColorRole.ToolTipBase: theme.surface,
            QPalette.ColorRole.ToolTipText: theme.text,
            QPalette.ColorRole.Shadow: theme.shadow,  # a button rising (hover.py)
        }
        for role, color in roles.items():
            palette.setColor(role, QColor(color))
        return palette


def active_theme() -> Theme:
    """The theme the application shows now, read from the palette ``ThemeManager`` applied.

    For widgets built on demand, like row menus, that would otherwise need a
    ``ThemeManager`` passed down through every row just to tint their icons.
    """
    window = QApplication.palette().color(QPalette.ColorRole.Window)
    return DARK if window == QColor(DARK.background) else LIGHT
