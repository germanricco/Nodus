"""Opening what lives outside Nodus: web pages in the browser, folders in Explorer."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_url(url: str) -> None:
    """Opens ``url`` in the default browser."""
    QDesktopServices.openUrl(QUrl(url))


def open_folder(folder: Path) -> None:
    """Shows ``folder`` in Windows Explorer, creating it if it is not there yet."""
    folder.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
