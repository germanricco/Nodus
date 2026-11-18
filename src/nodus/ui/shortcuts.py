"""Every keyboard and mouse shortcut of Nodus, in one table, by where it works.

Ayuda lists this table, and the widgets that answer a key ask its shortcut here
(``matches``), so the help says what the keys do and never promises one that does not
exist. Mouse gestures have no key: they are only told.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from nodus.i18n import N_

# A key counts when pressed alone; the keypad's Enter is still Enter.
_ALONE = Qt.KeyboardModifier.NoModifier | Qt.KeyboardModifier.KeypadModifier

ANYWHERE = N_("En toda la app")
LISTS = N_("En las listas")
FORMS = N_("En los formularios")
DETAILS = N_("En una cuenta, un beneficiario o una etiqueta")
TOUR = N_("En el recorrido guiado")
SHORTCUT_GROUPS = [ANYWHERE, LISTS, FORMS, DETAILS, TOUR]


@dataclass(frozen=True)
class Shortcut:
    """``keys`` are pressed together; each is drawn as a key of its own. ``qt_keys`` are
    the keys that do it, for the shortcuts a widget answers on its own. ``text``,
    ``group`` and the keys named with words are marked with ``N_()`` and translated
    where they are shown; ``label`` keeps the keys as Qt reads them."""

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


HELP = Shortcut(("F1",), N_("Abre o cierra la Ayuda."), ANYWHERE)
UNDO = Shortcut(("Ctrl", "Z"), N_("Deshace lo último."), ANYWHERE)
CLOSE_HELP = Shortcut(("Esc",), N_("Cierra la Ayuda."), ANYWHERE, (Qt.Key.Key_Escape,))
DELETE_ROWS = Shortcut((N_("Supr"),), N_("Borra las filas elegidas."), LISTS, (Qt.Key.Key_Delete,))
CLEAR_SELECTION = Shortcut(("Esc",), N_("Quita la selección."), LISTS, (Qt.Key.Key_Escape,))
BACK_TO_LIST = Shortcut(("Esc",), N_("Vuelve a la lista."), DETAILS, (Qt.Key.Key_Escape,))
TOUR_NEXT = Shortcut(
    ("→",),
    N_("Avanza (también Enter)."),
    TOUR,
    (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter),
)
TOUR_BACK = Shortcut(("←",), N_("Retrocede."), TOUR, (Qt.Key.Key_Left,))
TOUR_EXIT = Shortcut(("Esc",), N_("Sale del recorrido."), TOUR, (Qt.Key.Key_Escape,))

SHORTCUTS = [
    HELP,
    CLOSE_HELP,
    UNDO,
    Shortcut((N_("Doble clic"),), N_("Abre o edita la fila."), LISTS),
    Shortcut((N_("Clic derecho"),), N_("Abre el menú de la fila."), LISTS),
    Shortcut(("Ctrl", N_("clic")), N_("Suma o quita una fila."), LISTS),
    Shortcut((N_("Mayús"), N_("clic")), N_("Elige hasta esa fila."), LISTS),
    DELETE_ROWS,
    CLEAR_SELECTION,
    Shortcut(("Enter",), N_("Guarda."), FORMS),
    Shortcut(("Esc",), N_("Cierra; pregunta si cambiaste algo."), FORMS),
    BACK_TO_LIST,
    TOUR_NEXT,
    TOUR_BACK,
    TOUR_EXIT,
]
