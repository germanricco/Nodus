"""Errors say what happened and what to do; the system's text waits behind «Ver detalle»."""

from PySide6.QtGui import QGuiApplication

from nodus.ui.dialogs import export
from nodus.ui.dialogs.user_error import UserErrorDialog


def test_detail_is_folded_until_asked_for_and_can_be_copied(qtbot):
    dialog = UserErrorDialog("Exportar", "No se pudo guardar.", "Revisa la carpeta.", "acceso")
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.detail.isVisible()
    assert not dialog.detail.text.isVisible()
    dialog.detail.toggle_button.click()
    assert dialog.detail.text.isVisible()
    assert dialog.detail.toggle_button.text() == "Ocultar detalle"
    dialog.detail.copy_button.click()
    assert QGuiApplication.clipboard().text() == "acceso"
    assert dialog.detail.copy_button.text() == "Copiado"


def test_without_detail_there_is_no_link(qtbot):
    dialog = UserErrorDialog("Exportar", "No se pudo guardar.", "Revisa la carpeta.")
    qtbot.addWidget(dialog)
    dialog.show()

    assert not dialog.detail.isVisible()
    assert dialog.close_button.isDefault()


def test_failed_export_says_what_to_do(services, monkeypatch, tmp_path):
    def broken(_transactions, _path):
        raise PermissionError("[Errno 13] Permission denied")

    errors = []
    monkeypatch.setattr(services.export, "write_csv", broken)
    monkeypatch.setattr(
        export.QFileDialog, "getSaveFileName", lambda *a: (str(tmp_path / "x.csv"), "")
    )
    monkeypatch.setattr(export, "user_error", lambda *args: errors.append(args[2:]))

    assert export.export_transactions(None, services, [], "x.csv") is None
    what, how, detail = errors[0]
    assert what == "No se pudo guardar el archivo."
    assert "Excel" in how
    assert "Permission denied" in detail
