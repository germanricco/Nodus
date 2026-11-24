"""The arrow at the start of a row that holds others, which folds them under it."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from nodus.i18n import _
from nodus.ui.theme.design import ControlSize, IconSize
from nodus.ui.theme.icons import tinted_pixmap
from nodus.ui.theme.theme_manager import active_theme


class FoldButton(QPushButton):
    """Shows or hides the rows under ``name``: an arrow down while they show, to the right
    while folded, as the sidebar's groups. Only this button folds, so a double click on the
    row still opens it. Muted at rest, in the text color under the mouse, as the «⋯»."""

    fold_toggled = Signal(bool)  # folded

    WIDTH = IconSize.L + 2 * 2  # narrow: on every row it keeps its place, even unused

    def __init__(self, name: str, folded: bool) -> None:
        super().__init__()
        self._name = name
        self.setObjectName("FoldButton")
        self.setFixedSize(self.WIDTH, ControlSize.SMALL_BUTTON)
        self.setIconSize(QSize(IconSize.M, IconSize.M))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_folded(folded)
        self.clicked.connect(lambda: self.fold_toggled.emit(not self._folded))

    @property
    def folded(self) -> bool:
        return self._folded

    def set_folded(self, folded: bool) -> None:
        self._folded = folded
        text = (
            _("Mostrar las subcategorías de «{name}»")
            if folded
            else _("Ocultar las subcategorías de «{name}»")
        ).format(name=self._name)
        self.setToolTip(text)
        self.setAccessibleName(text)
        self._tint()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._tint()

    def _tint(self) -> None:
        theme = active_theme()
        name = "chevron-right" if self._folded else "chevron-down"
        result = QIcon(tinted_pixmap(name, theme.text_muted))
        result.addPixmap(tinted_pixmap(name, theme.text), QIcon.Mode.Active)
        self.setIcon(result)
