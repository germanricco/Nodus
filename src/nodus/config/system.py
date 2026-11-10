"""What Windows itself says about how the user wants the screen to behave."""

from __future__ import annotations

import ctypes
import sys

# SystemParametersInfo's action for «Show animations in Windows» (Accessibility).
SPI_GETCLIENTAREAANIMATION = 0x1042


def windows_animations_on() -> bool:
    """Whether Windows shows animations; true where it cannot be asked, so motion stays
    as designed unless the user turned it off."""
    if sys.platform != "win32":
        return True
    enabled = ctypes.c_bool(True)
    asked = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0
    )
    return bool(enabled.value) if asked else True
