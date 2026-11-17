"""Asks where to save a CSV export and writes it."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QFileDialog, QPushButton, QWidget

from nodus.models.period import Period
from nodus.models.transaction import Transaction
from nodus.services.container import Services
from nodus.ui.dialogs.user_error import user_error
from nodus.ui.text.labels import transactions_text
from nodus.ui.widgets.busy import busy
from nodus.ui.widgets.toast import show_toast

TITLE = "Exportar transacciones"

# Every exported file starts so, and says which movements it holds.
_EXPORT_PREFIX = "nodus-transacciones"


def export_filename(period: Period) -> str:
    """ "nodus-transacciones-2026-11.csv" for a month, start and end dates otherwise."""
    if period.is_whole_months and period.first_month == period.last_month:
        return f"{_EXPORT_PREFIX}-{period.start:%Y-%m}.csv"
    return f"{_EXPORT_PREFIX}-{period.start:%Y-%m-%d}_{period.end:%Y-%m-%d}.csv"


def all_transactions_filename(today: date) -> str:
    """ "nodus-transacciones-2026-11-17.csv": everything, as of ``today``."""
    return f"{_EXPORT_PREFIX}-{today:%Y-%m-%d}.csv"


def export_transactions(
    parent: QWidget,
    services: Services,
    transactions: list[Transaction],
    filename: str,
    button: QPushButton | None = None,
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
        with busy(button, "Exportando…"):
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
    count = len(transactions)
    show_toast(parent, f"Exportación lista: {transactions_text(count)}.")
    return path
