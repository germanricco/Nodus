"""Questions before acting: confirming a destructive action, or asking before a harmless one.

Every box is built here with its own buttons, named in Spanish: the static
``QMessageBox.information`` and ``warning`` show «OK», since Nodus loads no Qt translation.
"""

from collections.abc import Callable

from PySide6.QtCore import SignalInstance
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from nodus.i18n import _


def confirm(
    parent: QWidget,
    title: str,
    text: str,
    action: str | None = None,
    cancel_text: str | None = None,
) -> bool:
    """Asks the user to confirm; True only if they press ``action``, which is the title
    unless given ("Eliminar 3 transacciones").

    The button names what it does and shows in red, never a bare "Aceptar". "Cancelar" is
    the default button, so pressing Enter by reflex never destroys data.
    """
    box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=parent)
    accept_button = add_button(
        box, action or title, "DangerButton", QMessageBox.ButtonRole.DestructiveRole
    )
    cancel_button = add_button(
        box, cancel_text or _("Cancelar"), "SecondaryButton", QMessageBox.ButtonRole.RejectRole
    )
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is accept_button


def delete_with_confirm(
    parent: QWidget,
    title: str,
    text: str,
    delete: Callable[[], object],
    *changes: SignalInstance,
) -> bool:
    """Deletes from any page the same way: ``confirm`` with ``text``, which says what
    goes with it, then ``delete`` and the ``changes`` it makes. True if it was deleted.

    The copy before a large delete is made by the service, so no caller can forget it.
    """
    if not confirm(parent, title, text):
        return False
    delete()
    for change in changes:
        change.emit()
    return True


def tell(parent: QWidget, title: str, text: str, button: str | None = None) -> None:
    """Tells the user something that needs no answer, with one button in Spanish."""
    box = QMessageBox(QMessageBox.Icon.Information, title, text, parent=parent)
    box.setDefaultButton(
        add_button(
            box, button or _("Entendido"), "PrimaryButton", QMessageBox.ButtonRole.AcceptRole
        )
    )
    box.exec()


def ask(parent: QWidget, title: str, text: str, action: str, cancel: str | None = None) -> bool:
    """Asks before something that loses nothing; True only if they press ``action``.

    Unlike ``confirm``, the action is the primary button and the default one, since
    taking it by reflex does no harm. Esc and the ✕ answer ``cancel``.
    """
    box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=parent)
    accept_button = add_button(box, action, "PrimaryButton", QMessageBox.ButtonRole.AcceptRole)
    add_button(box, cancel or _("Cancelar"), "SecondaryButton", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(accept_button)
    box.exec()
    return box.clickedButton() is accept_button


def add_button(
    box: QMessageBox, text: str, style: str, role: QMessageBox.ButtonRole
) -> QPushButton:
    """Adds a button to ``box``, named for the stylesheet before it joins, since the box
    styles its buttons as they are added.

    The button is the box's child from the start. ``addButton`` does not take it over
    from Python, so a button nobody kept in a variable was collected and vanished: the
    box was left with its other button alone, which then also answered Esc and the ✕.
    """
    button = QPushButton(text, box)
    button.setObjectName(style)
    box.addButton(button, role)
    return button
