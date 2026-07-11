"""OpenCobol2 color theme system."""

from opencobol2.theming.builtins import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    DEFAULT_THEME_ID,
    HIGH_CONTRAST_DARK_THEME_ID,
    HIGH_CONTRAST_LIGHT_THEME_ID,
    LIGHT_THEME_ID,
)
from opencobol2.theming.models import (
    Theme,
    ThemeColors,
    ThemeKind,
)
from opencobol2.theming.registry import (
    ThemeAlreadyRegisteredError,
    ThemeNotFoundError,
    ThemeRegistry,
)


__all__ = [
    "create_builtin_theme_registry",
    "DARK_THEME_ID",
    "DEFAULT_THEME_ID",
    "HIGH_CONTRAST_DARK_THEME_ID",
    "HIGH_CONTRAST_LIGHT_THEME_ID",
    "LIGHT_THEME_ID",
    "Theme",
    "ThemeAlreadyRegisteredError",
    "ThemeColors",
    "ThemeKind",
    "ThemeNotFoundError",
    "ThemeRegistry",
]
