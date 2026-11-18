"""Restoring a copy of the data, from Ajustes or, on a new computer, from the Inicio."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QPushButton, QWidget

from nodus.i18n import N_, _
from nodus.services.container import Services
from nodus.services.errors import BackupError, ValidationError
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.dialogs.user_error import user_error
from nodus.ui.event_bus import EventBus
from nodus.ui.theme.theme import ThemeMode
from nodus.ui.theme.theme_manager import ThemeManager
from nodus.ui.widgets.busy import busy
from nodus.ui.widgets.toast import show_toast

TITLE = N_("Restaurar copia")


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
        parent, _("Restaurar desde una copia"), str(start_dir), _("Copias de Nodus (*.db)")
    )
    if not path:
        return False
    text = _(
        "Tus datos actuales se van a reemplazar por los de «{name}». Antes se"
        " guarda una copia de cómo están ahora, en la carpeta de copias."
    ).format(name=Path(path).name)
    if not confirm(parent, _(TITLE), text):
        return False
    try:
        with busy(button, _("Restaurando…")):
            services.backups.restore(Path(path), datetime.now())
    except ValidationError as error:
        user_error(
            parent, _(TITLE), str(error), _("Elige otra copia. Tus datos siguen como estaban.")
        )
        return False
    except BackupError as error:
        user_error(
            parent,
            _(TITLE),
            _("No se pudo restaurar la copia."),
            _(
                "Revisa que quede lugar en el disco y vuelve a intentarlo. Tus datos siguen"
                " como estaban."
            ),
            str(error),
        )
        return False
    # Whoever brings their data back has used Nodus: the tour is not offered, even
    # when the copy predates it.
    services.tour.mark_tour_offered()
    theme_manager.set_mode(ThemeMode.from_setting(services.settings.theme_preference()))
    event_bus.emit_all()
    show_toast(parent, _("Copia restaurada."))
    return True
