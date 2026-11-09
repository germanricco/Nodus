"""Small pill with how much a figure moved: "↗ 12 %" in green or "↘ 9 %" in red."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from nodus.ui.widgets.style import set_style_property


def format_change(change: float, unit: str = "%") -> str:
    """ "↗ 12 %", "↘ 9,5 %" or "→ 0 %", with one decimal only below 10. ``unit`` "pp"
    shows a change of a rate in percentage points."""
    percent = abs(change) * 100
    text = f"{percent:.1f}" if percent < 10 else f"{percent:.0f}"
    text = text.replace(".", ",").removesuffix(",0")
    arrow = "↗" if change > 0 else "↘" if change < 0 else "→"
    return f"{arrow} {text} {unit}"


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
            self._set_tone("empty")
            return
        self.setText(format_change(change, self._unit) + (f" · {detail}" if detail else ""))
        self.setVisible(True)
        good = change > 0 if self._higher_is_better else change < 0
        self._set_tone("neutral" if change == 0 else "good" if good else "bad")

    def _set_tone(self, tone: str) -> None:
        """Colors the pill; "empty" is a plain "—" without the pill or its padding."""
        if self.property("tone") == tone:
            return
        set_style_property(self, "tone", tone)
        # Re-polishing recolors the label but keeps the padding it had, and "empty" has
        # none. A new stylesheet of its own (a comment, one per tone) makes Qt recompute it.
        self.setStyleSheet(f"/* {tone} */")
