"""Asks where to save a CSV export and writes it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog, QWidget

from nodus.models.transaction import Transaction
from nodus.services.container import Services
from nodus.ui.dialogs.user_error import user_error

TITLE = "Exportar transacciones"


def export_transactions(
    parent: QWidget, services: Services, transactions: list[Transaction], filename: str
) -> Path | None:
    """Saves ``transactions`` to a CSV the user places, suggesting ``filename`` in Documents.

    Returns where it was saved, or None if the user cancelled or saving failed.
    """
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    chosen, _filter = QFileDialog.getSaveFileName(
        parent, TITLE, str(Path(documents) / filename), "Archivo CSV (*.csv)"
    )
    if not chosen:
        return None
    path = Path(chosen)
    try:
        services.export.write_csv(transactions, path)
    except OSError as error:
        user_error(
            parent,
            TITLE,
            "No se pudo guardar el archivo.",
            "Revisa que la carpeta exista, que puedas escribir en ella y que el archivo no"
            " esté abierto en otro programa, como Excel. Después vuelve a intentarlo.",
            str(error),
        )
        return None
    return path
