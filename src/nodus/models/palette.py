"""The preset colors of categories and tags."""

PALETTE = [
    "#e74c3c", "#e67e22", "#f39c12", "#f1c40f", "#2ecc71", "#27ae60",
    "#1abc9c", "#16a085", "#3498db", "#2980b9", "#8e44ad", "#95a5a6",
]  # fmt: skip


def palette_color(index: int) -> str:
    """The ``index``-th preset color, starting over after the last one."""
    return PALETTE[index % len(PALETTE)]
