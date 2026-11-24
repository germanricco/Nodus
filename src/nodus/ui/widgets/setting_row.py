"""One line of a settings card: what it is on the left, its controls on the right, or
under it when the card is too narrow for both."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QBoxLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.flow_layout import FlowLayout
from nodus.ui.widgets.style import hint_label, set_style_name


class SettingRow(QWidget):
    """A title with an optional short gray detail under it, and widgets aligned right.

    Keeps the settings readable at a glance: the explanation, when one is needed,
    goes in a tooltip instead of a paragraph.
    """

    def __init__(self, title: str, detail: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = layout = QHBoxLayout(self)
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
        controls = QWidget()
        # In lines too, so two controls wider than a narrow card go one under the other.
        self._controls = FlowLayout(controls, h_spacing=Space.S, v_spacing=Space.S)
        layout.addWidget(controls, alignment=Qt.AlignmentFlag.AlignVCenter)
        self._controls_box = controls
        self.set_detail(detail)

    def add(self, widget: QWidget) -> QWidget:
        """Appends a control on the right and returns it, so it can be kept in one line."""
        self._controls.addWidget(widget)
        # A control with no words of its own (a switch) is named by its row.
        if not widget.accessibleName() and not getattr(widget, "text", lambda: "")():
            widget.setAccessibleName(self.title.text())
        return widget

    @property
    def stacked(self) -> bool:
        """Whether the controls went under the title, for lack of width beside it."""
        return self._layout.direction() == QBoxLayout.Direction.TopToBottom

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """As narrow as the controls: past that, they go under the title."""
        hint = super().minimumSizeHint()
        margins = self._layout.contentsMargins()
        width = self._controls_box.minimumSizeHint().width() + margins.left() + margins.right()
        return QSize(min(hint.width(), width), hint.height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Decided by the controls' own width, never by the layout's: so it cannot swing.
        beside = Layout.SETTING_TITLE_MIN_WIDTH + self._layout.spacing()
        stack = event.size().width() < beside + self._controls_box.sizeHint().width()
        if stack != self.stacked:
            direction = QBoxLayout.Direction
            self._layout.setDirection(direction.TopToBottom if stack else direction.LeftToRight)
            alignment = Qt.AlignmentFlag.AlignLeft if stack else Qt.AlignmentFlag.AlignVCenter
            self._layout.setAlignment(self._controls_box, alignment)

    def set_detail(self, text: str, error: bool = False) -> None:
        """Shows ``text`` under the title (in the error color if ``error``); empty hides it."""
        self.detail.setText(text)
        self.detail.setVisible(bool(text))
        set_style_name(self.detail, "ErrorLabel" if error else "FieldHint")
