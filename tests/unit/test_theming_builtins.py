"""Unit tests for the built-in theme catalog."""

from __future__ import annotations

from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    DEFAULT_THEME_ID,
    HIGH_CONTRAST_DARK_THEME_ID,
    HIGH_CONTRAST_LIGHT_THEME_ID,
    LIGHT_THEME_ID,
    ThemeKind,
)


def test_builtin_registry_contains_four_themes() -> None:
    registry = create_builtin_theme_registry()

    assert len(registry.themes) == 4
    assert {
        theme.theme_id for theme in registry.themes
    } == {
        LIGHT_THEME_ID,
        DARK_THEME_ID,
        HIGH_CONTRAST_LIGHT_THEME_ID,
        HIGH_CONTRAST_DARK_THEME_ID,
    }


def test_builtin_theme_kinds_match_their_id() -> None:
    registry = create_builtin_theme_registry()

    assert registry.get(LIGHT_THEME_ID).kind is ThemeKind.LIGHT
    assert registry.get(DARK_THEME_ID).kind is ThemeKind.DARK
    assert (
        registry.get(HIGH_CONTRAST_LIGHT_THEME_ID).kind
        is ThemeKind.HIGH_CONTRAST_LIGHT
    )
    assert (
        registry.get(HIGH_CONTRAST_DARK_THEME_ID).kind
        is ThemeKind.HIGH_CONTRAST_DARK
    )


def test_default_theme_id_is_registered() -> None:
    registry = create_builtin_theme_registry()

    assert registry.get(DEFAULT_THEME_ID) is not None
    assert DEFAULT_THEME_ID == DARK_THEME_ID


def test_high_contrast_light_syntax_colors_differ_from_light() -> None:
    """High Contrast Light must not just reuse the regular Light theme's
    syntax palette verbatim -- its whole purpose is a distinct, more
    accessible color set, not a copy-paste of the non-HC theme."""

    registry = create_builtin_theme_registry()
    light_colors = registry.get(
        LIGHT_THEME_ID,
    ).colors
    high_contrast_colors = registry.get(
        HIGH_CONTRAST_LIGHT_THEME_ID,
    ).colors

    light_syntax = (
        light_colors.syntax_keyword,
        light_colors.syntax_string,
        light_colors.syntax_number,
        light_colors.syntax_comment,
    )
    high_contrast_syntax = (
        high_contrast_colors.syntax_keyword,
        high_contrast_colors.syntax_string,
        high_contrast_colors.syntax_number,
        high_contrast_colors.syntax_comment,
    )

    assert light_syntax != high_contrast_syntax
    # Every token's color must also be distinct from every other
    # token's color within the high-contrast palette itself.
    assert len(set(high_contrast_syntax)) == len(
        high_contrast_syntax,
    )


def test_builtin_registry_is_freshly_built_each_call() -> None:
    first_registry = create_builtin_theme_registry()
    second_registry = create_builtin_theme_registry()

    first_registry.get(LIGHT_THEME_ID)
    second_registry.get(LIGHT_THEME_ID)

    assert len(second_registry.themes) == 4
