"""Small helpers shared by widgets."""

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QObject, QPoint, Qt, QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QWidget,
)

from nodus.models.money import Money
from nodus.ui.theme.design import Elevation, Opacity, Popup
from nodus.ui.theme.theme import Theme

# Figures line up at their right edge, centered in their row.
RIGHT_ALIGNED = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def set_style_property(widget: QWidget, name: str, value: object) -> None:
    """Sets a property the stylesheet selects on (e.g. ``QLabel[tone="negative"]``).

    Qt does not re-evaluate stylesheets when a property changes, so the widget is re-polished.
    """
    widget.setProperty(name, value)
    _repolish(widget)


def make_hoverable(widget: QWidget) -> None:
    """Lights up ``widget``'s background under the mouse, as the sidebar's items do, so a
    row that can be clicked or has a menu shows it responds (``[hoverable="true"]`` in the
    stylesheet). Only for such rows: a row that lights up but does nothing misleads."""
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    widget.setAttribute(Qt.WidgetAttribute.WA_Hover)
    widget.setProperty("hoverable", True)


def set_style_name(widget: QWidget, name: str) -> None:
    """Gives ``widget`` the object name the stylesheet selects on (e.g. ``#ErrorLabel``)."""
    if widget.objectName() != name:
        widget.setObjectName(name)
        _repolish(widget)


def _repolish(widget: QWidget) -> None:
    """Qt does not re-evaluate stylesheets on its own when a selector's input changes."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def clear_layout(layout: QLayout) -> None:
    """Removes and deletes every widget in ``layout``, so it can be rebuilt from fresh data."""
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            # deleteLater waits for the event loop; hiding now keeps stale widgets out of sight.
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def elevate(widget: QWidget, theme: Theme) -> None:
    """Raises ``widget`` over the page with the one soft shadow of ``Elevation``."""
    color = QColor(theme.shadow)
    color.setAlphaF(Opacity.SHADOW)
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(Elevation.BLUR)
    shadow.setOffset(0, Elevation.OFFSET)
    shadow.setColor(color)
    widget.setGraphicsEffect(shadow)


def muted_label(text: str) -> QLabel:
    """A label in the quieter color, for what accompanies the main text."""
    label = QLabel(text)
    set_style_property(label, "muted", True)
    return label


def scrolling(widget: QWidget, horizontal: bool = True) -> QScrollArea:
    """``widget`` in a scroll area that follows its width; with ``horizontal`` off, the
    content is never wider than the area, so only a vertical bar ever shows."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    if not horizontal:
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


def secondary_button(text: str, on_click: Callable[[], object]) -> QPushButton:
    """A button for an action beside the main one, outlined rather than filled."""
    button = QPushButton(text)
    button.setObjectName("SecondaryButton")
    button.clicked.connect(on_click)
    return button


def amount_label(money: Money) -> QLabel:
    """``money`` written out, aligned with the amounts above and below it."""
    label = QLabel(money.format())
    label.setAlignment(RIGHT_ALIGNED)
    return label


def unit_animation(
    parent: QObject, easing: QEasingCurve.Type, on_value: Callable[[float], object]
) -> QVariantAnimation:
    """An animation from 0 to 1 that calls ``on_value`` on every step; who starts it sets
    its duration, from the motion scale."""
    animation = QVariantAnimation(parent)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(easing)
    animation.valueChanged.connect(on_value)
    return animation


def show_below(popup: QWidget, anchor: QWidget, align_right: bool = False) -> None:
    """Shows ``popup`` just under ``anchor``, sized to its content, with its left edge on
    the anchor's or, with ``align_right``, its right edge."""
    popup.adjustSize()
    x = anchor.width() if align_right else 0
    corner = anchor.mapToGlobal(QPoint(x, anchor.height() + Popup.PANEL_OFFSET))
    popup.move(corner.x() - (popup.width() if align_right else 0), corner.y())
    popup.show()
