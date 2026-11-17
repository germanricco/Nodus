"""Questions before acting: confirming a destructive action, or asking before a harmless one."""

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget


def confirm(
    parent: QWidget,
    title: str,
    text: str,
    action: str | None = None,
    cancel_text: str = "Cancelar",
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
        box, cancel_text, "SecondaryButton", QMessageBox.ButtonRole.RejectRole
    )
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is accept_button


def ask(parent: QWidget, title: str, text: str, action: str, cancel: str = "Cancelar") -> bool:
    """Asks before something that loses nothing; True only if they press ``action``.

    Unlike ``confirm``, the action is the primary button and the default one, since
    taking it by reflex does no harm. Esc and the ✕ answer ``cancel``.
    """
    box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=parent)
    accept_button = add_button(box, action, "PrimaryButton", QMessageBox.ButtonRole.AcceptRole)
    add_button(box, cancel, "SecondaryButton", QMessageBox.ButtonRole.RejectRole)
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
