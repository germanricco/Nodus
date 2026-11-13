"""Dialogs about account groups: naming a group, and choosing the group of an account."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget

from nodus.models.account import Account
from nodus.models.account_group import AccountGroup
from nodus.services.container import Services
from nodus.services.errors import ValidationError
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES, TYPE_NAME, FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.widgets.combo_box import ComboBox

# The item of the group list that creates a group on the spot.
NEW_GROUP = "new"
NO_GROUP = "Sin grupo"
GROUP_PLACEHOLDER = "Ej.: Bancos, Billeteras, Inversiones"


class GroupPicker:
    """The «Grupo» row of a form: «Sin grupo», each group and «Nuevo grupo…», which shows
    a row for the new group's name, so the first group is made without leaving the form."""

    def __init__(self, dialog: FormDialog, services: Services, current: int | None) -> None:
        self._dialog = dialog
        self._services = services
        self.input = ComboBox()
        self.input.addItem(NO_GROUP, None)
        for group in services.account_groups.list_groups():
            self.input.addItem(group.name, group.id)
        self.input.addItem("Nuevo grupo…", NEW_GROUP)
        self.input.setCurrentIndex(max(0, self.input.findData(current)))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(GROUP_PLACEHOLDER)
        dialog.form.addRow("Grupo", self.input)
        dialog.form.addRow("Nombre del grupo", self.name_input)
        dialog.bind_field(self.name_input, "group_name")
        self.input.currentIndexChanged.connect(self._show_name)
        self._show_name()

    @property
    def is_new(self) -> bool:
        return self.input.currentData() == NEW_GROUP

    def required(self) -> tuple[QWidget, str]:
        """The new group's name, required while it is shown."""
        return self.name_input, TYPE_NAME

    def group_id(self) -> int | None:
        """The chosen group, creating it first if it is a new one."""
        if not self.is_new:
            return self.input.currentData()
        try:
            return self._services.account_groups.create(self.name_input.text()).id
        except ValidationError as error:
            raise ValidationError(str(error), field="group_name") from error

    def _show_name(self) -> None:
        self._dialog.form.setRowVisible(self.name_input, self.is_new)
        if self.is_new:
            self.name_input.setFocus()


class GroupDialog(FormDialog):
    """Creates a group, or renames ``group`` when given."""

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        group: AccountGroup | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Renombrar grupo" if group else "Nuevo grupo",
            parent,
            SAVE_CHANGES if group else "Agregar grupo",
        )
        self._services = services
        self._event_bus = event_bus
        self._group = group
        self.name_input = QLineEdit(group.name if group else "")
        self.name_input.setPlaceholderText(GROUP_PLACEHOLDER)
        self.form.addRow("Nombre", self.name_input)
        self.bind_field(self.name_input, "name")

    def missing(self) -> dict[QWidget, str]:
        return self.required((self.name_input, TYPE_NAME))

    def save(self) -> None:
        if self._group:
            self._services.account_groups.rename(self._group.id, self.name_input.text())
        else:
            self._services.account_groups.create(self.name_input.text())
        self._event_bus.accounts_changed.emit()


class MoveToGroupDialog(FormDialog):
    """Puts ``account`` in another group, or in none."""

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        account: Account,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"Mover «{account.name}»", parent, "Mover")
        self._services = services
        self._event_bus = event_bus
        self._account = account
        self.group_picker = GroupPicker(self, services, account.group_id)

    def missing(self) -> dict[QWidget, str]:
        return self.required(self.group_picker.required())

    def save(self) -> None:
        group_id = self.group_picker.group_id()
        self._services.account_groups.move_account(self._account.id, group_id)
        self._event_bus.accounts_changed.emit()
