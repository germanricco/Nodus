"""Errors raised by services and the validations shared between them.

Error messages are in Spanish because the UI shows them to the user as they are.
"""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


class ValidationError(Exception):
    """The requested operation breaks a business rule. The message explains which."""


class NotFoundError(ValidationError):
    """The referenced record does not exist (for instance, it was deleted meanwhile)."""


class BackupError(Exception):
    """A copy of the data could not be written (a full disk, a locked folder…).

    Wraps the file or database error so callers above the services need not know
    which storage engine is underneath.
    """


class UpdateError(Exception):
    """A new version could not be downloaded or started. The message explains why."""


def require_found(value: T | None, message: str) -> T:
    """Returns ``value``, or raises ``NotFoundError`` with ``message`` if it is None."""
    if value is None:
        raise NotFoundError(message)
    return value


def clean_name(name: str) -> str:
    """Trims a user-typed name and rejects it if nothing is left."""
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("El nombre no puede estar vacío.")
    return cleaned
