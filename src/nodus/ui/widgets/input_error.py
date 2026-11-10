"""An error about what was typed in one field, which a form shows under that field."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from nodus.services.errors import ValidationError


class InputError(ValidationError):
    """``message`` about ``widget``: an amount that is not a number, a count out of range.

    The widget that reads its own text raises it, so the form needs no name to place the
    message, unlike the rules of the services (``ValidationError.field``).
    """

    def __init__(self, message: str, widget: QWidget) -> None:
        super().__init__(message)
        self.widget = widget
