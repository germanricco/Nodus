"""What Nodus says when the data file is damaged, before any window opens."""

from __future__ import annotations

from pathlib import Path

from nodus import APP_NAME
from nodus.i18n import N_, _
from nodus.models.period import format_date
from nodus.services.backups.recovery import RecoveryCopy
from nodus.ui.dialogs.user_error import UserErrorDialog, user_error

DAMAGED = N_("El archivo de tus datos está dañado.")
RESTORE = N_("Restaurar la copia")


def recovery_text(copy: RecoveryCopy) -> str:
    """What restoring ``copy`` brings back, and what it leaves out."""
    return _(
        "Nodus puede traer tus datos de vuelta desde la última copia sana, del"
        " {date} a las {time}. Lo que anotaste después"
        " no va a estar. El archivo dañado queda guardado aparte, junto a tus datos."
    ).format(date=format_date(copy.saved.date()), time=f"{copy.saved:%H:%M}")


def no_copy_text(backups_dir: Path) -> str:
    """Where a copy saved outside the computer has to go for Nodus to find it."""
    return _(
        "No hay una copia sana en «{folder}». Si guardaste una fuera de la PC, copia ese"
        " archivo a esa carpeta y vuelve a abrir Nodus."
    ).format(folder=backups_dir)


def offer_recovery(copy: RecoveryCopy | None, backups_dir: Path, detail: str) -> bool:
    """Tells that the data is damaged and offers to restore ``copy``; True if the user
    chose to. Without a copy, says where one could come from."""
    if copy is None:
        user_error(None, APP_NAME, _(DAMAGED), no_copy_text(backups_dir), detail)
        return False
    dialog = UserErrorDialog(APP_NAME, _(DAMAGED), recovery_text(copy), detail, action=_(RESTORE))
    return bool(dialog.exec())
