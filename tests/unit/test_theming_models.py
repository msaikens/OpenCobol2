"""Unit tests for color theme domain models."""

from __future__ import annotations

import pytest

from opencobol2.theming import (
    Theme,
    ThemeColors,
    ThemeKind,
)


def _create_colors(
    **overrides: str,
) -> ThemeColors:
    values = {
        "background": "#1E1E1E",
        "foreground": "#D4D4D4",
        "accent": "#007ACC",
        "selection_background": "#264F78",
        "selection_foreground": "#FFFFFF",
        "editor_background": "#1E1E1E",
        "editor_foreground": "#D4D4D4",
        "line_number_foreground": "#858585",
        "current_line_highlight": "#2A2A2A",
        "diagnostic_error": "#F14C4C",
        "diagnostic_warning": "#CCA700",
        "diagnostic_information": "#3794FF",
        "syntax_keyword": "#569CD6",
        "syntax_string": "#CE9178",
        "syntax_number": "#B5CEA8",
        "syntax_comment": "#6A9955",
    }
    values.update(overrides)

    return ThemeColors(**values)


def test_theme_colors_normalize_lowercase_hex() -> None:
    colors = _create_colors(
        accent="#abc123",
    )

    assert colors.accent == "#ABC123"


def test_theme_colors_reject_invalid_hex() -> None:
    with pytest.raises(
        ValueError,
        match="must use #RRGGBB format",
    ):
        _create_colors(
            accent="blue",
        )


def test_theme_colors_reject_non_string() -> None:
    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        _create_colors(
            accent=123,  # type: ignore[arg-type]
        )


def test_theme_requires_non_empty_id() -> None:
    with pytest.raises(
        ValueError,
        match="Theme ID must not be empty",
    ):
        Theme(
            theme_id="   ",
            display_name="Custom",
            kind=ThemeKind.DARK,
            colors=_create_colors(),
        )


def test_theme_normalizes_kind_from_string() -> None:
    theme = Theme(
        theme_id="custom",
        display_name="Custom",
        kind="dark",  # type: ignore[arg-type]
        colors=_create_colors(),
    )

    assert theme.kind is ThemeKind.DARK


def test_theme_requires_theme_colors_instance() -> None:
    with pytest.raises(
        TypeError,
        match="Theme colors must be ThemeColors",
    ):
        Theme(
            theme_id="custom",
            display_name="Custom",
            kind=ThemeKind.DARK,
            colors={},  # type: ignore[arg-type]
        )
