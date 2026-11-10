"""Color palettes for the light and dark themes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from nodus.models.money import Money


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
    accent: str  # fills and borders: the primary button, a chosen box, the focus
    accent_hover: str
    accent_soft: str
    accent_text: str  # the violet as text: the current page, a chosen tab or option
    on_accent: str  # text on the accent's fill: the primary button
    income: str
    income_soft: str
    expense: str
    expense_soft: str
    on_expense: str  # text on the expense's fill: the bell's count
    warning: str
    warning_soft: str
    # Series of a chart that are not the user's categories, e.g. the net worth by currency.
    chart_1: str
    chart_2: str
    chart_3: str
    chart_4: str

    def series(self) -> tuple[str, str, str, str]:
        return (self.chart_1, self.chart_2, self.chart_3, self.chart_4)

    def tokens(self) -> dict[str, str]:
        return asdict(self)

    def tone_color(self, tone: str) -> str:
        """The color of an amount's tone ("positive", "negative" or "neutral")."""
        return {"positive": self.income, "negative": self.expense}.get(tone, self.text)

    def amount_color(self, money: Money) -> str:
        """Green above zero, red below it, plain text at zero."""
        if money.is_zero:
            return self.text
        return self.expense if money.is_negative else self.income


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
    accent_text="#6d4fd6",
    on_accent="#ffffff",
    income="#1a7a44",
    income_soft="#e2f3e8",
    expense="#c53026",
    expense_soft="#fbe7e5",
    on_expense="#ffffff",
    warning="#97600b",
    warning_soft="#fbefdc",
    chart_1="#6d4fd6",
    chart_2="#1e8e4f",
    chart_3="#c47d0e",
    chart_4="#3498db",
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
    accent="#795ce9",
    accent_hover="#7055e3",
    accent_soft="#2c2640",
    accent_text="#9881ee",
    on_accent="#ffffff",
    income="#3fbf74",
    income_soft="#1b3326",
    expense="#ef6b60",
    expense_soft="#3b2325",
    on_expense="#16151a",
    warning="#e8a33d",
    warning_soft="#3a2e1c",
    chart_1="#8b72ec",
    chart_2="#3fbf74",
    chart_3="#e8a33d",
    chart_4="#3498db",
)
