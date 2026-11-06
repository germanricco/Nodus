"""Tags: labels that group transactions across categories, such as a trip."""

from __future__ import annotations

from dataclasses import dataclass

from nodus.models.payee import normalize_name


@dataclass(frozen=True)
class Tag:
    """A label with a color. Its name is unique once normalized, as a payee's."""

    id: int | None
    name: str
    color: str

    @property
    def normalized_name(self) -> str:
        return normalize_name(self.name)
