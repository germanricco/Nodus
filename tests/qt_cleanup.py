"""Frees the widgets a test leaves behind."""

from PySide6.QtCore import QCoreApplication, QEvent


def flush_deleted() -> None:
    """Deletes the widgets waiting on ``deleteLater``, which ``processEvents`` never does."""
    if QCoreApplication.instance() is not None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
