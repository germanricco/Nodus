"""Small pill with how much a figure moved: "↗ 12 %" in green or "↘ 9 %" in red."""

from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import QLabel, QWidget

from nodus.models.language_format import format_decimal, format_percent
from nodus.ui.widgets.style import set_style_property


def format_change(change: float, unit: str = "%") -> str:
    """ "↗ 12 %", "↘ 9,5 %" or "→ 0 %", with one decimal only below 10. ``unit`` "pp"
    shows a change of a rate in percentage points."""
    arrow = "↗" if change > 0 else "↘" if change < 0 else "→"
    number = _percent_number(change)
    return f"{arrow} " + (format_percent(number) if unit == "%" else f"{number} {unit}")


def format_signed_percent(change: float) -> str:
    """ "+1,2 %" or "-0,4 %": a part of a change, written as the badge writes it."""
    return f"{'-' if change < 0 else '+'}{format_percent(_percent_number(change))}"


def _percent_number(change: float) -> str:
    percent = abs(change) * 100
    return format_decimal(percent, 1 if percent < 10 else 0, drop_zero=True)


class Tone(Enum):
    """How a pill reads: well, a warning, badly, or just information. The values are the
    stylesheet's ``tone`` of ``ChangeBadge``."""

    GOOD = "good"
    WARNING = "warning"
    BAD = "bad"
    NEUTRAL = "neutral"


class ChangeBadge(QLabel):
    """Shows a relative change, green when it is good news and red when it is not.

    ``higher_is_better`` is False for expenses, where going up is bad. Without a change to
    show (nothing to compare with) it shows ``none_text``, or hides if that is empty.
    """

    def __init__(
        self,
        higher_is_better: bool = True,
        none_text: str = "",
        unit: str = "%",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ChangeBadge")
        self._higher_is_better = higher_is_better
        self._none_text = none_text
        self._unit = unit

    def set_higher_is_better(self, higher_is_better: bool) -> None:
        """For a badge whose figure changes meaning, as income versus expenses."""
        self._higher_is_better = higher_is_better

    def set_change(self, change: float | None, detail: str = "") -> None:
        """``detail`` is added after the percentage, e.g. "+$ 118.400"."""
        if change is None:
            self.setText(self._none_text)
            self.setVisible(bool(self._none_text))
            self._set_tone(None)
            return
        self.setText(format_change(change, self._unit) + (f" · {detail}" if detail else ""))
        self.setVisible(True)
        good = change > 0 if self._higher_is_better else change < 0
        self._set_tone(Tone.NEUTRAL if change == 0 else Tone.GOOD if good else Tone.BAD)

    def _set_tone(self, tone: Tone | None) -> None:
        """Colors the pill; without a tone it is a plain "—", without the pill or its
        padding (the stylesheet's "empty")."""
        tone = tone.value if tone else "empty"
        if self.property("tone") == tone:
            return
        set_style_property(self, "tone", tone)
        # Re-polishing recolors the label but keeps the padding it had, and "empty" has
        # none. A new stylesheet of its own (a comment, one per tone) makes Qt recompute it.
        self.setStyleSheet(f"/* {tone} */")  # qss-refresh


def status_pill(text: str, tone: Tone) -> QLabel:
    """A small pill colored by ``tone``, as the change badges."""
    label = QLabel(text)
    label.setObjectName("ChangeBadge")
    set_style_property(label, "tone", tone.value)
    return label
