"""One line of a settings card: what it is on the left, its controls on the right."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.ui.theme.design import Space
from nodus.ui.widgets.style import hint_label, set_style_name


class SettingRow(QWidget):
    """A title with an optional short gray detail under it, and widgets aligned right.

    Keeps the settings readable at a glance: the explanation, when one is needed,
    goes in a tooltip instead of a paragraph.
    """

    def __init__(self, title: str, detail: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, Space.XS, 0, Space.XS)
        layout.setSpacing(Space.S)
        texts = QVBoxLayout()
        texts.setSpacing(Space.XXS)
        self.title = QLabel(title)
        self.title.setObjectName("RowTitle")
        self.title.setWordWrap(True)  # in two lines in a narrow window, not past the card
        self.detail = hint_label(detail)
        self.detail.setWordWrap(True)
        texts.addWidget(self.title)
        texts.addWidget(self.detail)
        layout.addLayout(texts, stretch=1)
        self._controls = layout
        self.set_detail(detail)

    def add(self, widget: QWidget) -> QWidget:
        """Appends a control on the right and returns it, so it can be kept in one line."""
        # Centered at its height, so a detail in several lines does not stretch it.
        self._controls.addWidget(widget, alignment=Qt.AlignmentFlag.AlignVCenter)
        return widget

    def set_detail(self, text: str, error: bool = False) -> None:
        """Shows ``text`` under the title (in the error color if ``error``); empty hides it."""
        self.detail.setText(text)
        self.detail.setVisible(bool(text))
        set_style_name(self.detail, "ErrorLabel" if error else "FieldHint")
