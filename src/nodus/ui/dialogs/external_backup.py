"""Saving a copy of the data outside the computer, from Ajustes or from the reminder."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from nodus.services.container import Services
from nodus.services.errors import BackupError
from nodus.ui.dialogs.confirm import styled_button
from nodus.ui.event_bus import EventBus

TITLE = "Copia fuera de la PC"


def save_copy_outside(parent: QWidget, services: Services, event_bus: EventBus) -> bool:
    """Asks where to save the copy and saves it there; True once it is saved.

    The folder of the last time is offered first, when it is there (the pen drive is
    plugged in), so the monthly copy takes one click.
    """
    folder = choose_folder(parent, services)
    if folder is None:
        return False
    try:
        copy = services.backups.export_to(folder, date.today())
    except BackupError as error:
        QMessageBox.warning(
            parent,
            TITLE,
            f"No se pudo guardar la copia en {folder}. Revisa que el pendrive o el disco"
            f" sigan conectados y vuelve a intentarlo.\n\nDetalle: {error}",
        )
        return False
    event_bus.backups_changed.emit()
    QMessageBox.information(parent, TITLE, f"Se guardó «{copy.name}» en {folder}.")
    return True


def choose_folder(parent: QWidget, services: Services) -> Path | None:
    """The last folder, if the user keeps it, or one picked in the folder dialog."""
    last = services.backups.external_folder()
    if last is not None:
        box = QMessageBox(
            QMessageBox.Icon.Question,
            TITLE,
            f"¿Guardar la copia en {last}, como la última vez?",
            parent=parent,
        )
        here = styled_button("Guardar ahí", "PrimaryButton")
        box.addButton(here, QMessageBox.ButtonRole.AcceptRole)
        other = styled_button("Elegir otra carpeta…", "SecondaryButton")
        box.addButton(other, QMessageBox.ButtonRole.ActionRole)
        cancel = styled_button("Cancelar", "SecondaryButton")
        box.addButton(cancel, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(here)
        box.exec()
        if box.clickedButton() is here:
            return last
        if box.clickedButton() is not other:
            return None
    start = last or services.settings.external_backup_folder() or Path.home()
    path = QFileDialog.getExistingDirectory(
        parent, "Guardar copia en un pendrive, un disco externo o Drive", str(start)
    )
    return Path(path) if path else None
