"""Errors told the way the user needs them: what happened and what to do about it.

The technical text (the system's own message) never leads: it waits behind «Ver
detalle», where it can be copied for a bug report. ``QMessageBox.setDetailedText`` is
not used because its button reads «Show Details…» in English.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nodus import APP_NAME
from nodus.config.logs import error_lines
from nodus.i18n import N_, _
from nodus.ui.browser import open_folder, open_url
from nodus.ui.text.error_report import report_url
from nodus.ui.theme.design import Layout, Space
from nodus.ui.widgets.style import secondary_button

SHOW_DETAIL = N_("Ver detalle")
HIDE_DETAIL = N_("Ocultar detalle")
UNEXPECTED_WHAT = N_("Algo falló en Nodus.")
UNEXPECTED_HOW = N_(
    "Lo que estabas haciendo puede no haberse guardado: revísalo. Envía el reporte para que"
    " lo arreglemos: se abre en el navegador y lo lees antes de enviarlo."
)


class ErrorDetail(QWidget):
    """A «Ver detalle» link that unfolds the technical text, read-only, with «Copiar».

    Hidden altogether while there is no detail to show.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        self.toggle_button = QPushButton(_(SHOW_DETAIL))
        self.toggle_button.setObjectName("LinkButton")
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumHeight(Layout.ERROR_DETAIL_HEIGHT)
        layout.addWidget(self.text)
        self.copy_button = secondary_button(_("Copiar"), self.copy)
        layout.addWidget(self.copy_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.set_detail("")

    def set_detail(self, detail: str) -> None:
        self.text.setPlainText(detail)
        self.setVisible(bool(detail))
        self._unfold(False)

    def toggle(self) -> None:
        self._unfold(self.text.isHidden())

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.copy_button.setText(_("Copiado"))

    def _unfold(self, unfolded: bool) -> None:
        self.text.setVisible(unfolded)
        self.copy_button.setVisible(unfolded)
        self.copy_button.setText(_("Copiar"))
        self.toggle_button.setText(_(HIDE_DETAIL) if unfolded else _(SHOW_DETAIL))


class UserErrorDialog(QDialog):
    """What went wrong, as a title-like sentence; what to do, under it; the technical
    detail folded away; and «Cerrar».

    An error with one way out names it in ``action``: that button is then the main one
    and accepts, and «Cerrar» rejects.
    """

    def __init__(
        self,
        title: str,
        what: str,
        how: str,
        detail: str = "",
        parent: QWidget | None = None,
        *,
        action: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(Layout.MESSAGE_MIN_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XXL, Space.XL, Space.XXL, Space.XL)
        layout.setSpacing(Space.M)
        self.what_label = QLabel(what)
        self.what_label.setObjectName("DialogTitle")
        self.what_label.setWordWrap(True)
        layout.addWidget(self.what_label)
        self.how_label = QLabel(how)
        self.how_label.setWordWrap(True)
        layout.addWidget(self.how_label)
        self.detail = ErrorDetail()
        self.detail.set_detail(detail)
        layout.addWidget(self.detail)
        self.buttons = QHBoxLayout()
        self.buttons.addStretch()
        self.close_button = QPushButton(_("Cerrar"))
        self.buttons.addWidget(self.close_button)
        main_button = self.close_button
        if action is None:
            self.close_button.clicked.connect(self.accept)
        else:
            self.close_button.setObjectName("SecondaryButton")
            self.close_button.clicked.connect(self.reject)
            self.action_button = main_button = QPushButton(action)
            self.action_button.clicked.connect(self.accept)
            self.buttons.addWidget(self.action_button)
        main_button.setObjectName("PrimaryButton")
        main_button.setDefault(True)
        layout.addLayout(self.buttons)


class UnexpectedErrorDialog(UserErrorDialog):
    """An error Nodus did not expect, which is a fault of Nodus and not of the user:
    besides what to do, it offers «Enviar reporte», the comments form filled in with
    what failed and where, and «Abrir registros», the folder of the log.

    ``what`` and ``how`` default to an error in the middle of the work; one known to
    happen at a given moment, like updating the data, says it its own way.
    """

    def __init__(
        self,
        error: BaseException,
        logs_dir: Path,
        parent: QWidget | None = None,
        *,
        what: str | None = None,
        how: str | None = None,
    ) -> None:
        detail = "\n".join(error_lines(error))
        what = what or _(UNEXPECTED_WHAT)
        super().__init__(APP_NAME, what, how or _(UNEXPECTED_HOW), detail, parent)
        self.logs_button = secondary_button(_("Abrir registros"), lambda: open_folder(logs_dir))
        self.logs_button.setToolTip(_("La carpeta donde Nodus anota lo que pasó"))
        self.buttons.insertWidget(0, self.logs_button)
        self.report_button = secondary_button(
            _("Enviar reporte"), lambda: open_url(report_url(error))
        )
        self.report_button.setToolTip(
            _("Abre el formulario de comentarios con el reporte; lo lees antes de enviarlo")
        )
        self.buttons.insertWidget(self.buttons.indexOf(self.close_button), self.report_button)


def user_error(parent: QWidget | None, title: str, what: str, how: str, detail: str = "") -> None:
    """Tells the user that something failed: ``what`` happened, ``how`` to fix it, and
    the system's ``detail`` folded behind «Ver detalle»."""
    UserErrorDialog(title, what, how, detail, parent).exec()
