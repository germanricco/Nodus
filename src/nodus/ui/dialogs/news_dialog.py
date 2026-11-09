"""What a version brings: after an update, from Ajustes, or before downloading one."""

from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from nodus.services.changelog import ChangelogEntry
from nodus.services.update_service import Release
from nodus.ui.formatting import format_date

HEADING_SPACE = 20


def entries_markdown(entries: list[ChangelogEntry]) -> str:
    """The entries one after another, each under its version and date."""
    sections = []
    for entry in entries:
        heading = f"### Nodus {entry.version}"
        if entry.released is not None:
            heading += f" · {format_date(entry.released)}"
        sections.append(f"{heading}\n\n{entry.body}")
    return "\n\n".join(sections)


def _space_out_headings(text: QTextBrowser) -> None:
    """Room above each heading but the first, so one version ends visibly before the next.

    Markdown ignores the document's default style sheet, so the margin goes on the blocks.
    """
    block = text.document().firstBlock().next()
    while block.isValid():
        if block.blockFormat().headingLevel():
            cursor = QTextCursor(block)
            block_format = block.blockFormat()
            block_format.setTopMargin(HEADING_SPACE)
            cursor.setBlockFormat(block_format)
        block = block.next()


class NewsDialog(QDialog):
    """A title, the notes in Markdown and one way out.

    The notes of a version not installed yet come with «Actualizar»: choosing it accepts
    the dialog, and the caller starts the update.
    """

    def __init__(
        self,
        title: str,
        markdown: str,
        update: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        layout.addWidget(heading)

        self.text = QTextBrowser()
        self.text.setObjectName("NewsText")
        self.text.setOpenExternalLinks(True)
        self.text.setMarkdown(markdown)
        _space_out_headings(self.text)
        layout.addWidget(self.text, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.update_button: QPushButton | None = None
        if update:
            close = QPushButton("Cerrar")
            close.setObjectName("SecondaryButton")
            close.clicked.connect(self.reject)
            buttons.addWidget(close)
            self.update_button = main_button = QPushButton("Actualizar")
        else:
            main_button = QPushButton("Entendido")
        main_button.clicked.connect(self.accept)
        main_button.setObjectName("PrimaryButton")
        main_button.setDefault(True)
        buttons.addWidget(main_button)
        layout.addLayout(buttons)

    @classmethod
    def for_entries(
        cls, entries: list[ChangelogEntry], parent: QWidget | None = None
    ) -> NewsDialog:
        """The news of installed versions, newest first."""
        return cls("Novedades de Nodus", entries_markdown(entries), parent=parent)

    @classmethod
    def for_release(cls, release: Release, parent: QWidget | None = None) -> NewsDialog:
        """What a published version brings, before installing it."""
        notes = release.notes or "Esta versión no trae notas."
        return cls(f"Qué trae Nodus {release.version}", notes, update=True, parent=parent)
