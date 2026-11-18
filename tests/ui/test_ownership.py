"""A widget Python would collect in the app is collected in the tests too (``conftest``).

Python frees most objects at once, but one held only by a reference cycle waits for a
collection, which in Nodus comes at any moment: a helper kept that way works in a test
that never collects, and stops working for the user.
"""

import gc

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QPushButton, QVBoxLayout


class Counter(QObject):
    """Counts clicks. No Qt parent owns it: only its own cycle holds it."""

    def __init__(self) -> None:
        super().__init__()
        self.clicks = 0
        self.itself = self

    def count(self) -> None:
        self.clicks += 1


class ForgetfulDialog(QDialog):
    """Connects its button to a ``Counter`` it does not keep, the mistake to catch."""

    def __init__(self) -> None:
        super().__init__()
        self.button = QPushButton("Contar")
        QVBoxLayout(self).addWidget(self.button)
        self.button.clicked.connect(Counter().count)


def counters_alive() -> int:
    return sum(isinstance(obj, Counter) for obj in gc.get_objects())


def test_a_helper_held_by_a_cycle_alone_is_gone_once_the_dialog_is_registered(qtbot):
    dialog = ForgetfulDialog()
    assert counters_alive() == 1  # until a collection, as in a test that never makes one

    qtbot.addWidget(dialog)

    assert counters_alive() == 0
