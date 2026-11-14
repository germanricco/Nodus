"""Questions before acting: confirming a destructive action, or asking before a harmless one."""

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget


def confirm(parent: QWidget, title: str, text: str, action: str | None = None) -> bool:
    """Asks the user to confirm; True only if they press ``action``, which is the title
    unless given ("Eliminar 3 transacciones").

    The button names what it does and shows in red, never a bare "Aceptar". "Cancelar" is
    the default button, so pressing Enter by reflex never destroys data.
    """
    box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=parent)
    accept_button = styled_button(action or title, "DangerButton")
    box.addButton(accept_button, QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = styled_button("Cancelar", "SecondaryButton")
    box.addButton(cancel_button, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is accept_button


def ask(parent: QWidget, title: str, text: str, action: str, cancel: str = "Cancelar") -> bool:
    """Asks before something that loses nothing; True only if they press ``action``.

    Unlike ``confirm``, the action is the primary button and the default one, since
    taking it by reflex does no harm.
    """
    box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=parent)
    accept_button = styled_button(action, "PrimaryButton")
    box.addButton(accept_button, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(styled_button(cancel, "SecondaryButton"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(accept_button)
    box.exec()
    return box.clickedButton() is accept_button


def styled_button(text: str, style: str) -> QPushButton:
    """A button named for the stylesheet before it joins the box, which styles its
    buttons as they are added."""
    button = QPushButton(text)
    button.setObjectName(style)
    return button
