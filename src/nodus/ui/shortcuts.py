"""Every keyboard and mouse shortcut of Nodus, in one table.

Ayuda lists this table, so a shortcut added to the app is added here, and the help
never promises one that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Shortcut:
    keys: str
    text: str
    where: str


HELP = Shortcut("F1", "Abre la Ayuda.", "En cualquier página")

SHORTCUTS = [
    HELP,
    Shortcut("Enter", "Guarda el formulario.", "En los formularios"),
    Shortcut("Esc", "Cierra el formulario sin guardar.", "En los formularios"),
    Shortcut("Esc", "Vuelve a la lista.", "En la página de una cuenta, beneficiario o etiqueta"),
    Shortcut("Esc", "Quita la selección.", "En las listas"),
    Shortcut("Supr", "Elimina las filas elegidas, después de preguntar.", "En las listas"),
    Shortcut("Ctrl + clic", "Suma o quita una fila de la selección.", "En las listas"),
    Shortcut("Mayús + clic", "Elige todas las filas hasta esa.", "En las listas"),
    Shortcut("Doble clic", "Hace lo principal de la fila: abrirla o editarla.", "En las listas"),
    Shortcut("Clic derecho", "Abre el menú de la fila, igual que «⋯».", "En las listas"),
    Shortcut("← y →", "Retrocede y avanza.", "En el recorrido guiado"),
]
