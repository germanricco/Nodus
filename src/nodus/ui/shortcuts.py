"""Every keyboard and mouse shortcut of Nodus, in one table, by where it works.

Ayuda lists this table, and the widgets that answer a key ask its shortcut here
(``matches``), so the help says what the keys do and never promises one that does not
exist. Mouse gestures have no key: they are only told.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence

from nodus.i18n import N_, _
from nodus.ui.navigation import PageId

ANYWHERE = N_("En toda la app")
LISTS = N_("En las listas")
FORMS = N_("En los formularios")
DETAILS = N_("En una cuenta, un beneficiario o una etiqueta")
ROWS = N_("En las filas, con el teclado")
TOUR = N_("En el recorrido guiado")
SHORTCUT_GROUPS = [ANYWHERE, LISTS, ROWS, FORMS, DETAILS, TOUR]


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
    # How Qt reads the keys, when ``keys`` draws them otherwise (an arrow: «←», «Left»).
    qt_sequence: str = ""

    # The modifier its ``qt_keys`` go with (Alt for Alt+↑); none by default.
    modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
    # Keys that do the same with Mayús, such as Mayús+F10 for the Menu key.
    with_shift: tuple[Qt.Key, ...] = ()

    def matches(self, event: QKeyEvent) -> bool:
        """Whether ``event`` is one of this shortcut's keys, pressed alone or with its
        ``modifier`` (the keypad's Enter is still Enter)."""
        modifiers = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        key = Qt.Key(event.key())
        if key in self.with_shift:
            return modifiers == Qt.KeyboardModifier.ShiftModifier
        return modifiers == self.modifier and key in self.qt_keys

    @property
    def label(self) -> str:
        """As a tooltip writes it: «Ctrl+clic», «F1», «Alt+←»."""
        return "+".join(self.keys)

    @property
    def sequence(self) -> QKeySequence:
        """The keys for a ``QShortcut``."""
        return QKeySequence(self.qt_sequence or self.label)


def with_keys(text: str, keys: str) -> str:
    """``text`` followed by the keys that do it, as every tooltip of something with a
    shortcut ends: «Ayuda (F1)»."""
    return _("{action} ({keys})").format(action=text, keys=keys)


def page_keys() -> dict[PageId, str]:
    """Ctrl+1 to Ctrl+9 for the first nine pages of the sidebar, top to bottom (Ajustes
    sits at its foot)."""
    pages = [page_id for page_id in PageId if page_id is not PageId.SETTINGS]
    return {page_id: f"Ctrl+{number}" for number, page_id in enumerate(pages[:9], start=1)}


HELP = Shortcut(("F1",), N_("Abre o cierra la Ayuda."), ANYWHERE)
UNDO = Shortcut(("Ctrl", "Z"), N_("Deshace lo último."), ANYWHERE)
NEW_TRANSACTION = Shortcut(("Ctrl", "N"), N_("Agrega una transacción."), ANYWHERE)
SEARCH = Shortcut(
    ("Ctrl", "F"),
    N_("Busca en la página."),
    ANYWHERE,
)
HIDE_AMOUNTS = Shortcut(("Ctrl", "H"), N_("Oculta o muestra montos."), ANYWHERE)
COMMAND_PALETTE = Shortcut(
    ("Ctrl", "K"),
    N_("Busca adónde ir."),
    ANYWHERE,
)
GO_TO_PAGE = Shortcut(("Ctrl", "1…9"), N_("Va a una página."), ANYWHERE)
BACK = Shortcut(("Alt", "←"), N_("Vuelve a la página anterior."), ANYWHERE, qt_sequence="Alt+Left")
FORWARD = Shortcut(("Alt", "→"), N_("Va a la página siguiente."), ANYWHERE, qt_sequence="Alt+Right")
CLOSE_HELP = Shortcut(("Esc",), N_("Cierra la Ayuda."), ANYWHERE, (Qt.Key.Key_Escape,))
DELETE_ROWS = Shortcut((N_("Supr"),), N_("Borra las filas elegidas."), LISTS, (Qt.Key.Key_Delete,))
CLEAR_SELECTION = Shortcut(("Esc",), N_("Quita la selección."), LISTS, (Qt.Key.Key_Escape,))
BACK_TO_LIST = Shortcut(("Esc",), N_("Vuelve a la lista."), DETAILS, (Qt.Key.Key_Escape,))
OPEN_ROW = Shortcut(
    ("Enter",),
    N_("Abre o edita la fila."),
    ROWS,
    (Qt.Key.Key_Return, Qt.Key.Key_Enter),
)
ROW_MENU = Shortcut(
    (N_("Menú"),),
    N_("Abre el menú de la fila."),
    ROWS,
    (Qt.Key.Key_Menu,),
    with_shift=(Qt.Key.Key_F10,),
)
PREVIOUS_ROW = Shortcut(("↑",), N_("Va a la fila de arriba."), ROWS, (Qt.Key.Key_Up,))
NEXT_ROW = Shortcut(("↓",), N_("Va a la fila de abajo."), ROWS, (Qt.Key.Key_Down,))
FOLD_ROW = Shortcut(("←",), N_("Pliega un grupo."), ROWS, (Qt.Key.Key_Left,))
UNFOLD_ROW = Shortcut(("→",), N_("Despliega un grupo."), ROWS, (Qt.Key.Key_Right,))
MOVE_ROW_UP = Shortcut(
    ("Alt", "↑"),
    N_("Sube la cuenta en su grupo."),
    ROWS,
    (Qt.Key.Key_Up,),
    modifier=Qt.KeyboardModifier.AltModifier,
)
MOVE_ROW_DOWN = Shortcut(
    ("Alt", "↓"),
    N_("Baja la cuenta en su grupo."),
    ROWS,
    (Qt.Key.Key_Down,),
    modifier=Qt.KeyboardModifier.AltModifier,
)
SAVE_AND_ADD_ANOTHER = Shortcut(
    ("Ctrl", "Enter"),
    N_("Guarda y anota otra."),
    FORMS,
    qt_sequence="Ctrl+Return",
)
TOUR_NEXT = Shortcut(
    ("→",),
    N_("Avanza."),
    TOUR,
    (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter),
)
TOUR_BACK = Shortcut(("←",), N_("Retrocede."), TOUR, (Qt.Key.Key_Left,))
TOUR_EXIT = Shortcut(("Esc",), N_("Sale del recorrido."), TOUR, (Qt.Key.Key_Escape,))

SHORTCUTS = [
    COMMAND_PALETTE,
    NEW_TRANSACTION,
    SEARCH,
    GO_TO_PAGE,
    BACK,
    FORWARD,
    HIDE_AMOUNTS,
    HELP,
    CLOSE_HELP,
    UNDO,
    Shortcut((N_("Doble clic"),), N_("Abre o edita la fila."), LISTS),
    Shortcut((N_("Clic derecho"),), N_("Abre el menú de la fila."), LISTS),
    Shortcut(("Ctrl", N_("clic")), N_("Suma o quita una fila."), LISTS),
    Shortcut((N_("Mayús"), N_("clic")), N_("Elige hasta esa fila."), LISTS),
    DELETE_ROWS,
    CLEAR_SELECTION,
    OPEN_ROW,
    ROW_MENU,
    Shortcut((N_("Mayús"), "F10"), ROW_MENU.text, ROWS),
    PREVIOUS_ROW,
    NEXT_ROW,
    FOLD_ROW,
    UNFOLD_ROW,
    MOVE_ROW_UP,
    MOVE_ROW_DOWN,
    Shortcut(("Enter",), N_("Guarda."), FORMS),
    Shortcut(("Esc",), N_("Cierra el formulario."), FORMS),
    SAVE_AND_ADD_ANOTHER,
    BACK_TO_LIST,
    TOUR_NEXT,
    Shortcut(("Enter",), TOUR_NEXT.text, TOUR),
    TOUR_BACK,
    TOUR_EXIT,
]
