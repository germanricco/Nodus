"""Base for dialogs that edit data through a form."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, SignalInstance
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QCalendarWidget,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nodus.i18n import N_, _
from nodus.services.errors import ValidationError
from nodus.ui.dialogs.confirm import confirm
from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.inputs.input_error import InputError
from nodus.ui.widgets.inputs.tag_input import TagInput
from nodus.ui.widgets.style import secondary_button, set_style_property

# The main button of a dialog that edits something that already exists.
SAVE_CHANGES = N_("Guardar cambios")
# The red message under a field, and the property that gives the field a red border.
FIELD_ERROR = "FieldError"
ERROR_PROPERTY = "error"

# What a required field left empty asks for: «Elige» what is picked, «Escribe» what is
# typed. Every form uses these, so the same field asks the same way everywhere.
CHOOSE_ACCOUNT = N_("Elige una cuenta.")
CHOOSE_CATEGORY = N_("Elige una categoría.")
TYPE_NAME = N_("Escribe un nombre.")
TYPE_AMOUNT = N_("Escribe un monto.")
# What a list shows while nothing likely enough stands chosen (``set_placeholder``).
ACCOUNT_PLACEHOLDER = N_("Elegir cuenta")
CATEGORY_PLACEHOLDER = N_("Elegir categoría")
DISCARD_TITLE = N_("¿Descartar los cambios?")
DISCARD_TEXT = N_("Lo que cambiaste en este formulario no se guarda.")


@dataclass
class _FieldError:
    """A message shown under a field, and how to take it away when the field changes."""

    widget: QWidget
    label: QLabel
    signal: SignalInstance
    slot: Callable[..., None]


class FormDialog(QDialog):
    """A titled form with "Cancelar" and a main button, and an inline error message.

    The main button says what it does (``action``, already translated): "Agregar
    cuenta", or "Guardar cambios" when none is given.

    Subclasses add their fields to ``form`` and implement ``save``. A problem is shown
    under the field that causes it, in red, as a login form does, and the dialog stays
    open so the user can fix it without retyping everything:

    - ``missing`` lists the required fields left empty, each with its message; they are
      all shown at once, and ``save`` only runs when none is missing;
    - a ``ValidationError`` from ``save`` goes under the field its ``field`` names
      (``bind_field``), or at the foot of the dialog when it names none.

    A field's message goes away as soon as that field changes.

    Closing with changes (Cancelar, Esc or the ✕) asks before discarding them. What the
    dialog fills in by itself before it shows does not count, and neither does a field
    changed and then put back.

    The dialog always takes the size of its content, so it grows and shrinks as fields
    are shown or hidden instead of keeping the blank space of a larger mode.
    """

    MIN_WIDTH = Layout.DIALOG_MIN_WIDTH
    MARGIN = Space.XXL

    def __init__(
        self, title: str, parent: QWidget | None = None, action: str | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)

        layout = self._layout = QVBoxLayout(self)
        layout.setContentsMargins(self.MARGIN, Space.XL, self.MARGIN, Space.XL)
        layout.setSpacing(Space.L)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        # A fixed-size layout overrides the widget's minimum width; a strut keeps it.
        layout.addStrut(self.MIN_WIDTH - 2 * self.MARGIN)

        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        layout.addWidget(heading)

        self.form = QFormLayout()
        self.form.setSpacing(Space.M)
        layout.addLayout(self.form)
        self._fields: dict[str, QWidget] = {}
        self._shown_state: list[object] | None = None
        self._field_errors: list[_FieldError] = []

        self.error_label = QLabel()
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = self._buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = self._cancel_button = secondary_button(_("Cancelar"), self.reject)
        self.save_button = QPushButton(action or _(SAVE_CHANGES))
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._on_save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

    def add_above_form(self, widget: QWidget) -> None:
        """Places ``widget`` between the title and the form, e.g. a mode selector."""
        self._layout.insertWidget(1, widget)

    def add_below_form(self, widget: QWidget) -> None:
        """Places ``widget`` between the form and its foot, e.g. what was just saved."""
        self._layout.insertWidget(self._layout.indexOf(self.error_label), widget)

    def add_button(self, button: QPushButton) -> None:
        """Adds ``button`` to the foot, between «Cancelar» and the main button, and in
        that order for Tab too."""
        self._buttons.insertWidget(self._buttons.indexOf(self.save_button), button)
        self.setTabOrder(self._cancel_button, button)

    def submit(self) -> bool:
        """Checks the form and runs ``save``, showing what is missing or wrong under its
        field; True when it saved. The main button closes the dialog after it."""
        self.clear_errors()
        missing = self.missing()
        if missing:
            for widget, message in missing.items():
                self.show_field_error(widget, message)
            _input(next(iter(missing))).setFocus()
            return False
        try:
            self.save()
        except ValidationError as error:
            if isinstance(error, InputError):
                widget: QWidget | None = error.widget
            else:
                widget = self._fields.get(error.field or "")
            if widget is not None and self._is_shown(widget):
                self.show_field_error(widget, str(error))
                _input(widget).setFocus()
            else:
                self.show_error(str(error))
            return False
        return True

    def remember_state(self) -> None:
        """Counts what the fields hold now as unchanged: closing then asks nothing."""
        self._shown_state = self._form_state()

    def bind_field(self, widget: QWidget, *names: str) -> None:
        """Shows the errors about ``names`` (as ``ValidationError.field`` says them) under
        ``widget``, a field of the form or an input inside one."""
        for name in names:
            self._fields[name] = widget

    def missing(self) -> dict[QWidget, str]:
        """The required fields left empty, in the form's order, with what to do. Forms
        with required fields build it with ``required``."""
        return {}

    def required(self, *fields: tuple[QWidget, str]) -> dict[QWidget, str]:
        """Of ``fields`` (a field and what it asks for, translated), those left empty in a
        visible row: a field the current mode hides is not required."""
        return {
            widget: message
            for widget, message in fields
            if self._is_shown(widget) and is_empty(widget)
        }

    def save(self) -> None:
        """Stores the result. Raise ValidationError to keep the dialog open."""
        raise NotImplementedError

    def show_error(self, message: str) -> None:
        """A message about no single field, at the foot of the dialog."""
        self.error_label.setText(message)
        self.error_label.show()

    def show_field_error(self, widget: QWidget, message: str) -> None:
        """``message`` in red under the form row holding ``widget``, which gets a red
        border until it changes."""
        label = QLabel(message)
        label.setObjectName(FIELD_ERROR)
        label.setWordWrap(True)
        # A form spaces all its rows alike; room below the message keeps it with the
        # field above it instead of halfway to the next one.
        label.setContentsMargins(0, 0, 0, Space.S)
        self.form.insertRow(self._form_row(widget) + 1, "", label)
        _set_error(widget, True)
        signal = _changed_signal(widget)

        def clear(*_args: object) -> None:
            self._clear_field_error(widget)

        signal.connect(clear)
        self._field_errors.append(_FieldError(widget, label, signal, clear))

    def field_error(self, widget: QWidget) -> str | None:
        """The message shown under ``widget``, if any."""
        return next(
            (error.label.text() for error in self._field_errors if error.widget is widget), None
        )

    def clear_errors(self) -> None:
        self.error_label.hide()
        for error in list(self._field_errors):
            self._clear_field_error(error.widget)

    def has_changes(self) -> bool:
        """Whether a field differs from how it was when the dialog showed."""
        return self._shown_state is not None and self._form_state() != self._shown_state

    def reject(self) -> None:
        """Closes without saving, after asking if something changed."""
        if self.has_changes() and not confirm(
            self,
            _(DISCARD_TITLE),
            _(DISCARD_TEXT),
            _("Descartar"),
            cancel_text=_("Seguir editando"),
        ):
            return
        super().reject()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        self._align_labels()
        super().showEvent(event)
        if self._shown_state is None:
            self.remember_state()
            self._focus_first_field()

    def _focus_first_field(self) -> None:
        """Starts in the first field, ready to type, unless the dialog chose one. Qt
        would give the focus to the main button, whose focus ring is for the keyboard."""
        if not isinstance(self.focusWidget(), (QAbstractButton, type(None))):
            return
        widget = self.nextInFocusChain()
        while widget is not self:
            if (
                isinstance(widget, (QLineEdit, QComboBox, QDateEdit))
                and widget.isVisibleTo(self)
                and widget.isEnabled()
                and widget.focusPolicy() & Qt.FocusPolicy.TabFocus
            ):
                widget.setFocus(Qt.FocusReason.OtherFocusReason)
                return
            widget = widget.nextInFocusChain()

    def _form_state(self) -> list[object]:
        """What every field holds now, in the form's order, to tell later if any changed."""
        state: list[object] = []
        for widget in self.findChildren(QWidget):
            if any(isinstance(p, QCalendarWidget) for p in _ancestors(widget)):
                continue  # browsing the calendar's months changes no field
            if isinstance(widget, TagInput):
                state.append(widget.names())
            elif isinstance(widget, QLineEdit):
                state.append(widget.text())
            elif isinstance(widget, QComboBox):
                state.append(widget.currentText())
            elif isinstance(widget, QDateEdit):
                state.append(widget.date())
            elif isinstance(widget, QAbstractButton) and widget.isCheckable():
                state.append(widget.isChecked())
        return state

    def _align_labels(self) -> None:
        """Gives every label the width of the longest one, hidden rows included.

        A form sizes its label column from the visible labels only, so showing or hiding
        a row (like switching between Gasto, Ingreso and Transferencia) would shift the
        fields sideways.
        """
        labels = [
            item.widget()
            for row in range(self.form.rowCount())
            if (item := self.form.itemAt(row, QFormLayout.ItemRole.LabelRole))
            and isinstance(item.widget(), QLabel)
        ]
        width = max((label.sizeHint().width() for label in labels), default=0)
        for label in labels:
            label.setMinimumWidth(width)

    def _on_save(self) -> None:
        if self.submit():
            self.accept()

    def _form_row(self, widget: QWidget) -> int:
        """The form row holding ``widget``, itself a field or inside one."""
        current: QWidget | None = widget
        while current is not None:
            row, _role = self.form.getWidgetPosition(current)
            if row >= 0:
                return row
            current = current.parentWidget()
        raise ValueError("The widget is not in the form")

    def _is_shown(self, widget: QWidget) -> bool:
        """Whether ``widget`` is in a visible row, where a message under it can be seen."""
        try:
            return self.form.isRowVisible(self._form_row(widget))
        except ValueError:
            return False

    def _clear_field_error(self, widget: QWidget) -> None:
        for error in [error for error in self._field_errors if error.widget is widget]:
            error.signal.disconnect(error.slot)
            _set_error(widget, False)
            self.form.removeRow(error.label)
            self._field_errors.remove(error)


def _ancestors(widget: QWidget) -> list[QWidget]:
    found = []
    parent = widget.parentWidget()
    while parent is not None:
        found.append(parent)
        parent = parent.parentWidget()
    return found


def _input(widget: QWidget) -> QWidget:
    """What the user types or picks in: the widget itself, or the line edit of a
    composite field such as an amount."""
    if isinstance(widget, (QLineEdit, QComboBox, QDateEdit)):
        return widget
    line_edit = getattr(widget, "line_edit", None)
    return line_edit if isinstance(line_edit, QLineEdit) else widget


def is_empty(widget: QWidget) -> bool:
    """Nothing typed in a text field, or nothing chosen in a list."""
    field = _input(widget)
    if isinstance(field, QComboBox):
        return field.currentIndex() < 0 or field.currentData() is None
    if isinstance(field, QLineEdit):
        return not field.text().strip()
    return False


def _changed_signal(widget: QWidget) -> SignalInstance:
    """The signal that says the user changed ``widget``."""
    field = _input(widget)
    if isinstance(field, QComboBox):
        return field.currentIndexChanged
    if isinstance(field, QDateEdit):
        return field.dateChanged
    if isinstance(field, QLineEdit):
        return field.textChanged
    if isinstance(field, QAbstractItemView):
        return field.selectionModel().selectionChanged
    return widget.changed


def _set_error(widget: QWidget, on: bool) -> None:
    """The red border of a field in error, through the stylesheet's ``[error="true"]``."""
    set_style_property(_input(widget), ERROR_PROPERTY, on)
