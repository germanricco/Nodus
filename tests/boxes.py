"""Helpers to answer a real question box in tests, as the user would."""

import gc

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def answer_box(how: str, buttons: list[str] | None = None) -> None:
    """Answers the box about to open: with the button named ``how``, "Esc" or "close"
    (the ✕). Python collects first, so a button the box does not own is gone by then,
    as it would be for the user; ``buttons`` gets the texts of those left."""

    def act():
        gc.collect()
        box = QApplication.activeModalWidget()
        if buttons is not None:
            buttons.extend(button.text() for button in box.buttons())
        if how == "Esc":
            QTest.keyClick(box, Qt.Key.Key_Escape)
        elif how == "close":
            box.close()
        else:
            next(b for b in box.buttons() if b.text() == how).click()

    QTimer.singleShot(0, act)
