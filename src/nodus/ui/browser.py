"""Opening web pages in the user's browser."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_url(url: str) -> None:
    """Opens ``url`` in the default browser."""
    QDesktopServices.openUrl(QUrl(url))
