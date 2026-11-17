"""Errors raised by services and the validations shared between them.

Error messages are in Spanish because the UI shows them to the user as they are.
"""

from __future__ import annotations

from datetime import date
from typing import TypeVar

from nodus.models.money import Money
from nodus.models.period import FIRST_DAY, LAST_DAY

T = TypeVar("T")

TOO_LARGE_TEXT = "El monto es demasiado grande."
OUT_OF_CALENDAR_TEXT = f"La fecha tiene que estar entre {FIRST_DAY.year} y {LAST_DAY.year}."


class ValidationError(Exception):
    """The requested operation breaks a business rule. The message explains which.

    ``field`` names the piece of data at fault, as the draft calls it (``"amount"``,
    ``"to_account_id"``, ``"name"``…), so a form can show the message under that field;
    None when the rule involves no single one.
    """

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class NotFoundError(ValidationError):
    """The referenced record does not exist (for instance, it was deleted meanwhile)."""


class BackupError(Exception):
    """A copy of the data could not be written (a full disk, a locked folder…).

    Wraps the file or database error so callers above the services need not know
    which storage engine is underneath.
    """


class UpdateError(Exception):
    """A new version could not be downloaded or started.

    The message is written for the user; ``detail`` keeps the system's own text, for
    whoever needs to report the problem.
    """

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


def require_found(value: T | None, message: str) -> T:
    """Returns ``value``, or raises ``NotFoundError`` with ``message`` if it is None."""
    if value is None:
        raise NotFoundError(message)
    return value


def clean_name(name: str) -> str:
    """Trims a user-typed name and rejects it if nothing is left."""
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("El nombre no puede estar vacío.", field="name")
    return cleaned


def require_storable(amount: Money, field: str | None = None) -> None:
    """Rejects an amount beyond ``MAX_UNITS``: saved, it would break the balances."""
    if not amount.is_storable:
        raise ValidationError(TOO_LARGE_TEXT, field=field)


def require_in_calendar(day: date, field: str | None = None) -> None:
    """Rejects a day outside ``FIRST_DAY``–``LAST_DAY``, from which later dates (the next
    charge, the last installment) could not be computed."""
    if not FIRST_DAY <= day <= LAST_DAY:
        raise ValidationError(OUT_OF_CALENDAR_TEXT, field=field)
