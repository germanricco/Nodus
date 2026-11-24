"""A button that stands for an action rises under the mouse and sinks while held."""

import pytest
from PySide6.QtCore import QEvent, QMargins, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from nodus.ui.theme.design import Lift, set_reduced_motion
from nodus.ui.theme.hover import LIFTED, rise_of, shadow_of


@pytest.fixture
def button(qtbot, theme_manager, animations):
    """At the right end of a row with no margins, as a page's header buttons are, in a
    page with room around the row."""
    page = QWidget()
    qtbot.addWidget(page)
    page.resize(400, 200)
    row = QWidget()
    QHBoxLayout(row).setContentsMargins(0, 0, 0, 0)
    button = QPushButton("Agregar grupo")
    button.setObjectName("SecondaryButton")
    row.layout().addStretch()
    row.layout().addWidget(button)
    QVBoxLayout(page).setContentsMargins(40, 40, 40, 40)
    page.layout().addWidget(row)
    page.layout().addStretch()
    # Shown but not on screen: the mouse is only the events a test sends, without the
    # platform's own enters and leaves.
    page.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    page.show()
    yield button  # while ``page`` lives


def enter(button) -> None:
    point = QPointF(5, 5)
    QApplication.sendEvent(button, QEnterEvent(point, point, button.mapToGlobal(point)))


def leave(button) -> None:
    QApplication.sendEvent(button, QEvent(QEvent.Type.Leave))


def press(button) -> None:
    point = QPointF(5, 5)
    QApplication.sendEvent(
        button,
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            point,
            button.mapToGlobal(point),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),  # fmt: skip
    )


def settle(qtbot, button, height: float) -> None:
    qtbot.waitUntil(lambda: rise_of(button).height == pytest.approx(height), timeout=2000)


def test_it_rises_under_the_mouse_and_sinks_while_held(qtbot, button):
    enter(button)
    settle(qtbot, button, 1.0)
    assert shadow_of(button).height_ == pytest.approx(1.0)

    press(button)
    settle(qtbot, button, Lift.HELD)
    assert shadow_of(button).height_ == pytest.approx(Lift.HELD)


def test_its_shadow_is_not_cut_by_the_row_that_ends_with_it(qtbot, button):
    """Qt cuts what a widget draws at its parent's edge: the shadow goes in the first
    container with room around the button, and lets the mouse through."""
    enter(button)
    shadow = shadow_of(button)
    host = shadow.parentWidget()

    assert host is not button.parentWidget()
    around = QRect(button.mapTo(host, QPoint(0, 0)), button.size())
    reach = Lift.BLUR + Lift.OFFSET
    assert shadow.geometry() == around.marginsAdded(QMargins(reach, reach, reach, reach))
    assert host.rect().contains(shadow.geometry())
    assert shadow.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_at_rest_or_hidden_it_has_no_shadow(qtbot, button):
    enter(button)
    settle(qtbot, button, 1.0)
    leave(button)
    settle(qtbot, button, 0.0)
    assert shadow_of(button) is None

    enter(button)
    QApplication.sendEvent(button, QEvent(QEvent.Type.Hide))  # its page goes away
    assert shadow_of(button) is None


def test_icons_and_links_answer_with_their_color_alone(qtbot, button):
    assert "IconButton" not in LIFTED and "MoreButton" not in LIFTED
    button.setObjectName("IconButton")

    enter(button)

    assert rise_of(button) is None


def test_nothing_rises_with_less_motion_or_disabled(qtbot, button):
    set_reduced_motion(True)  # the user's «Reducir animaciones»; the suite turns it back
    enter(button)
    assert rise_of(button) is None
    set_reduced_motion(False)

    button.setEnabled(False)
    enter(button)
    assert rise_of(button) is None
