"""Every keyboard and mouse shortcut of Nodus, in one table, by where it works.

Ayuda lists this table, and the widgets that answer a key ask its shortcut here
(``matches``), so the help says what the keys do and never promises one that does not
exist. Mouse gestures have no key: they are only told.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

# A key counts when pressed alone; the keypad's Enter is still Enter.
_ALONE = Qt.KeyboardModifier.NoModifier | Qt.KeyboardModifier.KeypadModifier

ANYWHERE = "En toda la app"
LISTS = "En las listas"
FORMS = "En los formularios"
DETAILS = "En la página de una cuenta, un beneficiario o una etiqueta"
TOUR = "En el recorrido guiado"
SHORTCUT_GROUPS = [ANYWHERE, LISTS, FORMS, DETAILS, TOUR]


@dataclass(frozen=True)
class Shortcut:
    """``keys`` are pressed together; each is drawn as a key of its own. ``qt_keys`` are
    the keys that do it, for the shortcuts a widget answers on its own."""

    keys: tuple[str, ...]
    text: str
    group: str
    qt_keys: tuple[Qt.Key, ...] = ()

    def matches(self, event: QKeyEvent) -> bool:
        """Whether ``event`` is one of this shortcut's keys, pressed alone."""
        alone = not event.modifiers() & ~_ALONE
        return alone and Qt.Key(event.key()) in self.qt_keys

    @property
    def label(self) -> str:
        """As a tooltip or ``QKeySequence`` writes it: «Ctrl+clic», «F1»."""
        return "+".join(self.keys)


HELP = Shortcut(("F1",), "Abre o cierra la Ayuda, en el tema de la página donde estás.", ANYWHERE)
UNDO = Shortcut(("Ctrl", "Z"), "Deshace lo último que hiciste, si avisó «Deshacer».", ANYWHERE)
CLOSE_HELP = Shortcut(("Esc",), "Cierra la Ayuda.", ANYWHERE, (Qt.Key.Key_Escape,))
DELETE_ROWS = Shortcut(
    ("Supr",), "Elimina las filas elegidas, después de preguntar.", LISTS, (Qt.Key.Key_Delete,)
)
CLEAR_SELECTION = Shortcut(("Esc",), "Quita la selección.", LISTS, (Qt.Key.Key_Escape,))
BACK_TO_LIST = Shortcut(("Esc",), "Vuelve a la lista.", DETAILS, (Qt.Key.Key_Escape,))
TOUR_NEXT = Shortcut(
    ("→",),
    "Avanza; también con Enter.",
    TOUR,
    (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter),
)
TOUR_BACK = Shortcut(("←",), "Retrocede.", TOUR, (Qt.Key.Key_Left,))
TOUR_EXIT = Shortcut(("Esc",), "Sale del recorrido.", TOUR, (Qt.Key.Key_Escape,))

SHORTCUTS = [
    HELP,
    CLOSE_HELP,
    UNDO,
    Shortcut(("Doble clic",), "Hace lo principal de la fila: abrirla o editarla.", LISTS),
    Shortcut(("Clic derecho",), "Abre el menú de la fila, igual que «⋯».", LISTS),
    Shortcut(("Ctrl", "clic"), "Suma o quita una fila de la selección.", LISTS),
    Shortcut(("Mayús", "clic"), "Elige todas las filas hasta esa.", LISTS),
    DELETE_ROWS,
    CLEAR_SELECTION,
    Shortcut(("Enter",), "Guarda.", FORMS),
    Shortcut(("Esc",), "Cierra sin guardar; si cambiaste algo, pregunta antes.", FORMS),
    BACK_TO_LIST,
    TOUR_NEXT,
    TOUR_BACK,
    TOUR_EXIT,
]
