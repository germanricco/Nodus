"""How every row of a list is laid out, so lists read alike on every page.

A row takes the height of its ``RowRole`` and centers what it holds in it, with the
same room at its sides and between its pieces (``RowSpace``); the rows of a list touch,
the height being their air. Tables take the same heights (``table.py``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from nodus.ui.theme.design import RowRole, RowSpace


def row_layout(row: QWidget, role: RowRole | None, indent: int = 0) -> QHBoxLayout:
    """Lays ``row`` out as a row of ``role``, its pieces from left to right; ``indent``
    pushes them right, under a group. The height is a minimum, so wrapped text still
    fits, with ``RowSpace.EDGE`` above and below. Without a role the row is part of a
    taller one (a budget's name over its bar): no height and no room above or below."""
    layout = QHBoxLayout(row)
    edge = 0 if role is None else RowSpace.EDGE
    layout.setContentsMargins(RowSpace.SIDE + indent, edge, RowSpace.SIDE, edge)
    layout.setSpacing(RowSpace.GAP)
    if role is not None:
        row.setMinimumHeight(role)
    return layout


def row_lines() -> QVBoxLayout:
    """A title over its detail, held together and centered in the row's height."""
    lines = QVBoxLayout()
    lines.setSpacing(0)
    lines.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    return lines


def row_list() -> QVBoxLayout:
    """A column of rows that touch, as every list stacks them."""
    rows = QVBoxLayout()
    rows.setContentsMargins(0, 0, 0, 0)
    rows.setSpacing(0)
    return rows
