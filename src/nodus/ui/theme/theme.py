"""Color palettes for the light and dark themes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class ThemeMode(Enum):
    """The user's theme preference. SYSTEM follows the operating system's setting."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"

    @classmethod
    def from_setting(cls, value: str | None) -> ThemeMode:
        """The saved preference; SYSTEM when none was saved or the value is unknown."""
        try:
            return cls(value)
        except ValueError:
            return cls.SYSTEM


@dataclass(frozen=True)
class Theme:
    """Named colors ("tokens") used by the stylesheet and by widgets that paint themselves.

    Styling refers to these names instead of raw colors, so both themes share one stylesheet.
    """

    name: str
    background: str
    surface: str
    sidebar: str
    border: str
    hover: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_soft: str
    on_accent: str
    income: str
    income_soft: str
    expense: str
    expense_soft: str
    warning: str
    warning_soft: str

    def tokens(self) -> dict[str, str]:
        return asdict(self)


# Inspired by MoneyMatter: warm neutral surfaces with a violet accent.
LIGHT = Theme(
    name="light",
    background="#f6f5f2",
    surface="#ffffff",
    sidebar="#fbfaf8",
    border="#e7e4dd",
    hover="#efede8",
    text="#1f1d1a",
    text_muted="#6b6760",
    accent="#6d4fd6",
    accent_hover="#5e40c7",
    accent_soft="#ece8fb",
    on_accent="#ffffff",
    income="#1e8e4f",
    income_soft="#e2f3e8",
    expense="#d9453b",
    expense_soft="#fbe7e5",
    warning="#c47d0e",
    warning_soft="#fbefdc",
)

DARK = Theme(
    name="dark",
    background="#16151a",
    surface="#1f1e24",
    sidebar="#1a191e",
    border="#2e2c35",
    hover="#27252d",
    text="#ecebef",
    text_muted="#9a98a3",
    accent="#8b72ec",
    accent_hover="#9d87f0",
    accent_soft="#2c2640",
    on_accent="#ffffff",
    income="#3fbf74",
    income_soft="#1b3326",
    expense="#ef6b60",
    expense_soft="#3b2325",
    warning="#e8a33d",
    warning_soft="#3a2e1c",
)
