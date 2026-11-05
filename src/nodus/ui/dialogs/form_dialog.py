"""Base for dialogs that edit data through a form."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nodus.services.errors import ValidationError


class FormDialog(QDialog):
    """A titled form with Cancelar/Guardar buttons and an inline error message.

    Subclasses add their fields to ``form`` and implement ``save``. If ``save`` raises
    ``ValidationError``, its message appears inside the dialog and the dialog stays open,
    so the user can fix the data without retyping everything.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        layout = self._layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        layout.addWidget(heading)

        self.form = QFormLayout()
        self.form.setSpacing(10)
        layout.addLayout(self.form)

        self.error_label = QLabel()
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("Guardar")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

    def add_above_form(self, widget: QWidget) -> None:
        """Places ``widget`` between the title and the form, e.g. a mode selector."""
        self._layout.insertWidget(1, widget)

    def save(self) -> None:
        """Validates the fields and stores the result. Raise ValidationError to keep it open."""
        raise NotImplementedError

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _on_save(self) -> None:
        try:
            self.save()
        except ValidationError as error:
            self.show_error(str(error))
            return
        self.accept()
