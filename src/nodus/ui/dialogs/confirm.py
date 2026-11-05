"""Confirmation before destructive actions."""

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm(parent: QWidget, title: str, text: str, action: str = "Eliminar") -> bool:
    """Asks the user to confirm; True only if they press ``action``.

    "Cancelar" is the default button, so pressing Enter by reflex never destroys data.
    """
    box = QMessageBox(QMessageBox.Icon.Warning, title, text, parent=parent)
    accept_button = box.addButton(action, QMessageBox.ButtonRole.DestructiveRole)
    cancel_button = box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is accept_button
