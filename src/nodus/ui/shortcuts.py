"""Every keyboard and mouse shortcut of Nodus, in one table, by where it works.

Ayuda lists this table, so a shortcut added to the app is added here, and the help
never promises one that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass

ANYWHERE = "En toda la app"
LISTS = "En las listas"
FORMS = "En los formularios"
DETAILS = "En la página de una cuenta, un beneficiario o una etiqueta"
TOUR = "En el recorrido guiado"
SHORTCUT_GROUPS = [ANYWHERE, LISTS, FORMS, DETAILS, TOUR]


@dataclass(frozen=True)
class Shortcut:
    """``keys`` are pressed together; each is drawn as a key of its own."""

    keys: tuple[str, ...]
    text: str
    group: str

    @property
    def label(self) -> str:
        """As a tooltip or ``QKeySequence`` writes it: «Ctrl+clic», «F1»."""
        return "+".join(self.keys)


HELP = Shortcut(("F1",), "Abre o cierra la Ayuda, en el tema de la página donde estás.", ANYWHERE)
UNDO = Shortcut(("Ctrl", "Z"), "Deshace lo último que hiciste, si avisó «Deshacer».", ANYWHERE)

SHORTCUTS = [
    HELP,
    UNDO,
    Shortcut(("Doble clic",), "Hace lo principal de la fila: abrirla o editarla.", LISTS),
    Shortcut(("Clic derecho",), "Abre el menú de la fila, igual que «⋯».", LISTS),
    Shortcut(("Ctrl", "clic"), "Suma o quita una fila de la selección.", LISTS),
    Shortcut(("Mayús", "clic"), "Elige todas las filas hasta esa.", LISTS),
    Shortcut(("Supr",), "Elimina las filas elegidas, después de preguntar.", LISTS),
    Shortcut(("Esc",), "Quita la selección.", LISTS),
    Shortcut(("Enter",), "Guarda.", FORMS),
    Shortcut(("Esc",), "Cierra sin guardar.", FORMS),
    Shortcut(("Esc",), "Vuelve a la lista.", DETAILS),
    Shortcut(("→",), "Avanza; también con Enter.", TOUR),
    Shortcut(("←",), "Retrocede.", TOUR),
    Shortcut(("Esc",), "Sale del recorrido.", TOUR),
]
