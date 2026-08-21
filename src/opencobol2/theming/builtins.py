"""Built-in color theme catalog.

Defines the light, dark, high-contrast light, and high-contrast dark
themes shipped with the application, and a factory that assembles
them into a ready-to-use :class:`~opencobol2.theming.registry.ThemeRegistry`.
"""

from __future__ import annotations

from opencobol2.theming.models import (
    Theme,
    ThemeColors,
    ThemeKind,
)
from opencobol2.theming.registry import ThemeRegistry


LIGHT_THEME_ID = "light"
DARK_THEME_ID = "dark"
HIGH_CONTRAST_LIGHT_THEME_ID = "high_contrast_light"
HIGH_CONTRAST_DARK_THEME_ID = "high_contrast_dark"

DEFAULT_THEME_ID = DARK_THEME_ID


def _create_light_theme() -> Theme:
    """Create the built-in light theme.

    :returns: A new :class:`Theme` describing the light color scheme.
    """

    return Theme(
        theme_id=LIGHT_THEME_ID,
        display_name="Light",
        kind=ThemeKind.LIGHT,
        colors=ThemeColors(
            background="#FFFFFF",
            foreground="#1E1E1E",
            accent="#005FB8",
            selection_background="#ADD6FF",
            selection_foreground="#000000",
            editor_background="#FFFFFF",
            editor_foreground="#1E1E1E",
            line_number_foreground="#237893",
            current_line_highlight="#F3F3F3",
            diagnostic_error="#E51400",
            diagnostic_warning="#BF8803",
            diagnostic_information="#1A85FF",
            syntax_keyword="#0000FF",
            syntax_string="#A31515",
            syntax_number="#098658",
            syntax_comment="#008000",
        ),
    )


def _create_dark_theme() -> Theme:
    """Create the built-in dark theme.

    :returns: A new :class:`Theme` describing the dark color scheme.
    """

    return Theme(
        theme_id=DARK_THEME_ID,
        display_name="Dark",
        kind=ThemeKind.DARK,
        colors=ThemeColors(
            background="#1E1E1E",
            foreground="#D4D4D4",
            accent="#007ACC",
            selection_background="#264F78",
            selection_foreground="#FFFFFF",
            editor_background="#1E1E1E",
            editor_foreground="#D4D4D4",
            line_number_foreground="#858585",
            current_line_highlight="#2A2A2A",
            diagnostic_error="#F14C4C",
            diagnostic_warning="#CCA700",
            diagnostic_information="#3794FF",
            syntax_keyword="#569CD6",
            syntax_string="#CE9178",
            syntax_number="#B5CEA8",
            syntax_comment="#6A9955",
        ),
    )


def _create_high_contrast_light_theme() -> Theme:
    """Create the built-in high-contrast light theme.

    The syntax palette is distinct from the regular Light theme's and
    each color was individually verified at WCAG AAA contrast
    (>= 7:1) against this theme's #FFFFFF background. The regular
    Light theme's ``syntax_number`` (#098658) is only 4.6:1, which
    fails AAA and has no business in a theme whose whole purpose is
    maximum contrast.

    :returns: A new :class:`Theme` describing the high-contrast light
        color scheme.
    """

    return Theme(
        theme_id=HIGH_CONTRAST_LIGHT_THEME_ID,
        display_name="High Contrast Light",
        kind=ThemeKind.HIGH_CONTRAST_LIGHT,
        colors=ThemeColors(
            background="#FFFFFF",
            foreground="#000000",
            accent="#0000FF",
            selection_background="#0000FF",
            selection_foreground="#FFFFFF",
            editor_background="#FFFFFF",
            editor_foreground="#000000",
            line_number_foreground="#000000",
            current_line_highlight="#E0E0E0",
            diagnostic_error="#FF0000",
            diagnostic_warning="#B35900",
            diagnostic_information="#0000FF",
            syntax_keyword="#0000FF",
            syntax_string="#8B0000",
            syntax_number="#006400",
            syntax_comment="#444444",
        ),
    )


def _create_high_contrast_dark_theme() -> Theme:
    """Create the built-in high-contrast dark theme.

    :returns: A new :class:`Theme` describing the high-contrast dark
        color scheme.
    """

    return Theme(
        theme_id=HIGH_CONTRAST_DARK_THEME_ID,
        display_name="High Contrast Dark",
        kind=ThemeKind.HIGH_CONTRAST_DARK,
        colors=ThemeColors(
            background="#000000",
            foreground="#FFFFFF",
            accent="#FFFF00",
            selection_background="#FFFF00",
            selection_foreground="#000000",
            editor_background="#000000",
            editor_foreground="#FFFFFF",
            line_number_foreground="#FFFFFF",
            current_line_highlight="#1A1A1A",
            diagnostic_error="#FF0000",
            diagnostic_warning="#FFFF00",
            diagnostic_information="#00FFFF",
            syntax_keyword="#3399FF",
            syntax_string="#FFA500",
            syntax_number="#90EE90",
            syntax_comment="#C0C0C0",
        ),
    )


def create_builtin_theme_registry() -> ThemeRegistry:
    """Create a registry pre-populated with the built-in theme catalog.

    :returns: A new :class:`ThemeRegistry` containing the light, dark,
        high-contrast light, and high-contrast dark built-in themes.
    """

    registry = ThemeRegistry()

    for factory in (
        _create_light_theme,
        _create_dark_theme,
        _create_high_contrast_light_theme,
        _create_high_contrast_dark_theme,
    ):
        registry.register(
            factory(),
        )

    return registry
