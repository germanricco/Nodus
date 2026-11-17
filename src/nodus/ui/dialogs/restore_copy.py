"""Restoring a copy of the data, from Ajustes or, on a new computer, from the Inicio."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QPushButton, QWidget

from nodus.services.container import Services
from nodus.services.errors import BackupError, ValidationError
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.user_error import user_error
from nodus.ui.event_bus import EventBus
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.busy import busy
from nodus.ui.widgets.toast import show_toast

TITLE = "Restaurar copia"


def restore_copy(
    parent: QWidget,
    services: Services,
    event_bus: EventBus,
    theme_manager: ThemeManager,
    start_dir: Path,
    button: QPushButton | None = None,
) -> bool:
    """Asks for a copy, starting in ``start_dir``, and replaces the data with it after
    confirming; True once it is restored. Every page reads the data anew, and the theme
    saved in the copy is applied."""
    path, _filter = QFileDialog.getOpenFileName(
        parent, "Restaurar desde una copia", str(start_dir), "Copias de Nodus (*.db)"
    )
    if not path:
        return False
    text = (
        f"Tus datos actuales se van a reemplazar por los de «{Path(path).name}». Antes se"
        " guarda una copia de cómo están ahora, en la carpeta de copias."
    )
    if not confirm(parent, TITLE, text):
        return False
    try:
        with busy(button, "Restaurando…"):
            services.backups.restore(Path(path), datetime.now())
    except ValidationError as error:
        user_error(parent, TITLE, str(error), "Elige otra copia. Tus datos siguen como estaban.")
        return False
    except BackupError as error:
        user_error(
            parent,
            TITLE,
            "No se pudo restaurar la copia.",
            "Revisa que quede lugar en el disco y vuelve a intentarlo. Tus datos siguen"
            " como estaban.",
            str(error),
        )
        return False
    theme_manager.set_mode(ThemeMode.from_setting(services.settings.theme_preference()))
    event_bus.emit_all()
    show_toast(parent, "Copia restaurada.")
    return True
