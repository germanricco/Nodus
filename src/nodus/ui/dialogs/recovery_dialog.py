"""What Nodus says when the data file is damaged, before any window opens."""

from __future__ import annotations

from pathlib import Path

from nodus import APP_NAME
from nodus.models.period import format_date
from nodus.services.backups.recovery import RecoveryCopy
from nodus.ui.dialogs.user_error import UserErrorDialog, user_error

DAMAGED = "El archivo de tus datos está dañado."
RESTORE = "Restaurar la copia"


def recovery_text(copy: RecoveryCopy) -> str:
    """What restoring ``copy`` brings back, and what it leaves out."""
    return (
        f"Nodus puede traer tus datos de vuelta desde la última copia sana, del"
        f" {format_date(copy.saved.date())} a las {copy.saved:%H:%M}. Lo que anotaste después"
        " no va a estar. El archivo dañado queda guardado aparte, junto a tus datos."
    )


def no_copy_text(backups_dir: Path) -> str:
    """Where a copy saved outside the computer has to go for Nodus to find it."""
    return (
        f"No hay una copia sana en «{backups_dir}». Si guardaste una fuera de la PC, copia ese"
        " archivo a esa carpeta y vuelve a abrir Nodus."
    )


def offer_recovery(copy: RecoveryCopy | None, backups_dir: Path, detail: str) -> bool:
    """Tells that the data is damaged and offers to restore ``copy``; True if the user
    chose to. Without a copy, says where one could come from."""
    if copy is None:
        user_error(None, APP_NAME, DAMAGED, no_copy_text(backups_dir), detail)
        return False
    dialog = UserErrorDialog(APP_NAME, DAMAGED, recovery_text(copy), detail, action=RESTORE)
    return bool(dialog.exec())
