"""The tags field of the transaction dialog."""

from factories import light_theme
from PySide6.QtCore import Qt

from nodus.models.transaction_filter import TransactionFilter
from nodus.ui.dialogs.transaction_dialog import TRANSFER_MODE, TransactionDialog
from nodus.ui.widgets.tag_input import TagInput, new_names_hint


def make_input(qtbot, services) -> TagInput:
    tag_input = TagInput(services.tags)
    qtbot.addWidget(tag_input)
    return tag_input


def chip_texts(tag_input) -> list[str]:
    layout = tag_input._chips_layout
    return [
        layout.itemAt(i).widget().text() for i in range(layout.count()) if layout.itemAt(i).widget()
    ]


def test_enter_and_comma_add_chips(qtbot, services):
    tag_input = make_input(qtbot, services)

    tag_input.line_edit.setText("Viaje")
    qtbot.keyClick(tag_input.line_edit, Qt.Key.Key_Return)
    tag_input.line_edit.setText("Casa")
    tag_input.line_edit.textEdited.emit("Casa, Auto")

    assert tag_input.names() == ("Viaje", "Casa", "Auto")
    assert chip_texts(tag_input) == ["Viaje  ✕", "Casa  ✕"]  # "Auto" is still being typed
    assert tag_input.hint.text() == "Se crearán «Viaje» y «Casa»"


def test_existing_tag_keeps_its_spelling_and_no_duplicates(qtbot, services):
    services.tags.create("Vacaciones")
    tag_input = make_input(qtbot, services)

    tag_input.add("vacaciones")
    tag_input.add("VACACIONES")

    assert tag_input.names() == ("Vacaciones",)
    assert tag_input.hint.isHidden()


def test_suggestions_leave_out_chosen_tags(qtbot, services):
    services.tags.create("Viaje")
    services.tags.create("Vivienda")
    tag_input = make_input(qtbot, services)
    tag_input.add("Viaje")

    tag_input.names_completer.suggest("vi")

    assert tag_input.names_completer.suggestions.stringList() == ["Vivienda"]


def test_chip_click_and_backspace_remove(qtbot, services):
    tag_input = make_input(qtbot, services)
    tag_input.set_names(["Viaje", "Casa", "Auto"])

    tag_input._chips_layout.itemAt(0).widget().click()
    qtbot.keyClick(tag_input.line_edit, Qt.Key.Key_Backspace)

    assert tag_input.names() == ("Casa",)


def test_new_names_hint():
    assert new_names_hint([]) == ""
    assert new_names_hint(["A"]) == "Se creará «A»"
    assert new_names_hint(["A", "B", "C"]) == "Se crearán «A», «B» y «C»"


def make_dialog(qtbot, services, event_bus, transaction=None) -> TransactionDialog:
    dialog = TransactionDialog(services, event_bus, light_theme(), transaction)
    qtbot.addWidget(dialog)
    return dialog


def test_dialog_saves_and_loads_tags(qtbot, services, event_bus, pesos):
    dialog = make_dialog(qtbot, services, event_bus)
    dialog.amount_input.line_edit.setText("100")
    dialog.tag_input.add("Viaje")
    dialog.tag_input.line_edit.setText("Trabajo")  # typed, not yet added

    with qtbot.waitSignal(event_bus.tags_changed):
        qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    (saved,) = services.transactions.list_transactions(TransactionFilter())
    edit = make_dialog(qtbot, services, event_bus, saved)
    assert edit.tag_input.names() == ("Trabajo", "Viaje")


def test_enter_in_the_tags_box_does_not_save(qtbot, services, event_bus, pesos):
    dialog = make_dialog(qtbot, services, event_bus)
    dialog.show()
    dialog.amount_input.line_edit.setText("100")
    dialog.tag_input.line_edit.setText("Viaje")

    qtbot.keyClick(dialog.tag_input.line_edit, Qt.Key.Key_Return)

    assert dialog.isVisible()
    assert services.transactions.list_transactions(TransactionFilter()) == []
    assert dialog.tag_input.names() == ("Viaje",)


def test_tags_row_is_hidden_for_transfers(qtbot, services, event_bus, pesos):
    dialog = make_dialog(qtbot, services, event_bus)

    dialog.mode_input.set_index(TRANSFER_MODE)

    assert not dialog.form.isRowVisible(dialog.tag_input)
