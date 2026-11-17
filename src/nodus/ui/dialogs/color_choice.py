"""The color field of the category and tag forms, which share the recent colors."""

from nodus.services.container import Services
from nodus.ui.widgets.color import ColorPicker


def color_picker(services: Services) -> ColorPicker:
    """A picker that offers the colors chosen lately, besides the palette."""
    return ColorPicker(services.settings.recent_colors())


def remember_color(services: Services, color: str) -> None:
    """Called on saving: a color outside the palette becomes the most recent one."""
    services.settings.add_recent_color(color)
