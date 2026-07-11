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


def test_builtin_registry_is_freshly_built_each_call() -> None:
    first_registry = create_builtin_theme_registry()
    second_registry = create_builtin_theme_registry()

    first_registry.get(LIGHT_THEME_ID)
    second_registry.get(LIGHT_THEME_ID)

    assert len(second_registry.themes) == 4
