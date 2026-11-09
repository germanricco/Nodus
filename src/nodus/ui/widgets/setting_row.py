"""One line of a settings card: what it is on the left, its controls on the right."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.ui.widgets.style import set_style_name


class SettingRow(QWidget):
    """A title with an optional short gray detail under it, and widgets aligned right.

    Keeps the settings readable at a glance: the explanation, when one is needed,
    goes in a tooltip instead of a paragraph.
    """

    def __init__(self, title: str, detail: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("RowTitle")
        self.detail = QLabel(detail)
        self.detail.setObjectName("FieldHint")
        self.detail.setWordWrap(True)
        texts.addWidget(self.title)
        texts.addWidget(self.detail)
        layout.addLayout(texts, stretch=1)
        self._controls = layout
        self.set_detail(detail)

    def add(self, widget: QWidget) -> QWidget:
        """Appends a control on the right and returns it, so it can be kept in one line."""
        self._controls.addWidget(widget)
        return widget

    def set_detail(self, text: str, error: bool = False) -> None:
        """Shows ``text`` under the title (in the error color if ``error``); empty hides it."""
        self.detail.setText(text)
        self.detail.setVisible(bool(text))
        set_style_name(self.detail, "ErrorLabel" if error else "FieldHint")
