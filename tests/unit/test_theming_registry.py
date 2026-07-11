"""Unit tests for the color theme registry."""

from __future__ import annotations

import pytest

from opencobol2.theming import (
    Theme,
    ThemeAlreadyRegisteredError,
    ThemeColors,
    ThemeKind,
    ThemeNotFoundError,
    ThemeRegistry,
)


def _create_theme(
    theme_id: str = "custom",
) -> Theme:
    return Theme(
        theme_id=theme_id,
        display_name="Custom",
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
        ),
    )


def test_registry_starts_empty() -> None:
    registry = ThemeRegistry()

    assert registry.themes == ()


def test_registry_registers_and_returns_theme() -> None:
    registry = ThemeRegistry()
    theme = _create_theme()

    registry.register(theme)

    assert registry.get("custom") is theme
    assert registry.themes == (theme,)


def test_registry_rejects_duplicate_id() -> None:
    registry = ThemeRegistry()
    registry.register(_create_theme())

    with pytest.raises(
        ThemeAlreadyRegisteredError,
        match="custom",
    ):
        registry.register(
            _create_theme(),
        )


def test_registry_raises_for_unknown_theme() -> None:
    registry = ThemeRegistry()

    with pytest.raises(
        ThemeNotFoundError,
        match="unknown",
    ):
        registry.get("unknown")


def test_registry_rejects_non_theme_registration() -> None:
    registry = ThemeRegistry()

    with pytest.raises(
        TypeError,
        match="Registered theme must be Theme",
    ):
        registry.register(
            object(),  # type: ignore[arg-type]
        )
