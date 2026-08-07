"""Unit tests for GUI theme palette application."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

from opencobol2.gui.theming import (
    apply_theme_to_widget,
    build_palette,
)
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    HIGH_CONTRAST_DARK_THEME_ID,
    HIGH_CONTRAST_LIGHT_THEME_ID,
    LIGHT_THEME_ID,
)


def _srgb_to_linear(
    channel: float,
) -> float:
    normalized = channel / 255.0
    return (
        normalized / 12.92
        if normalized <= 0.03928
        else ((normalized + 0.055) / 1.055) ** 2.4
    )


def _relative_luminance(
    color: QColor,
) -> float:
    return (
        0.2126
        * _srgb_to_linear(
            color.red(),
        )
        + 0.7152
        * _srgb_to_linear(
            color.green(),
        )
        + 0.0722
        * _srgb_to_linear(
            color.blue(),
        )
    )


def _wcag_contrast(
    color_a: QColor,
    color_b: QColor,
) -> float:
    lighter, darker = sorted(
        (
            _relative_luminance(
                color_a,
            ),
            _relative_luminance(
                color_b,
            ),
        ),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_build_palette_maps_theme_colors(
    qapp,
) -> None:
    theme = create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )

    palette = build_palette(
        theme,
    )

    assert (
        palette.color(
            QPalette.ColorRole.Window,
        ).name().upper()
        == theme.colors.background
    )
    assert (
        palette.color(
            QPalette.ColorRole.WindowText,
        ).name().upper()
        == theme.colors.foreground
    )


def test_build_palette_sets_tooltip_colors(
    qapp,
) -> None:
    theme = create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )

    palette = build_palette(
        theme,
    )

    assert (
        palette.color(
            QPalette.ColorRole.ToolTipBase,
        ).name().upper()
        == theme.colors.background
    )
    assert (
        palette.color(
            QPalette.ColorRole.ToolTipText,
        ).name().upper()
        == theme.colors.foreground
    )


def test_build_palette_gives_bevel_roles_real_contrast_against_window(
    qapp,
) -> None:
    theme = create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )

    palette = build_palette(
        theme,
    )
    window_value = (
        palette.color(
            QPalette.ColorRole.Window,
        )
        .lightness()
    )

    # Light/Midlight must be lighter than the window; Dark/Mid/Shadow
    # must be darker -- otherwise dock separators and splitter handles
    # render with no visible contrast against the surrounding panels.
    assert (
        palette.color(
            QPalette.ColorRole.Light,
        ).lightness()
        > window_value
    )
    assert (
        palette.color(
            QPalette.ColorRole.Midlight,
        ).lightness()
        > window_value
    )
    assert (
        palette.color(
            QPalette.ColorRole.Dark,
        ).lightness()
        < window_value
    )
    assert (
        palette.color(
            QPalette.ColorRole.Mid,
        ).lightness()
        < window_value
    )
    assert (
        palette.color(
            QPalette.ColorRole.Shadow,
        ).lightness()
        < window_value
    )


def test_build_palette_dims_disabled_text_distinctly(
    qapp,
) -> None:
    theme = create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )

    palette = build_palette(
        theme,
    )

    enabled_text = palette.color(
        QPalette.ColorGroup.Active,
        QPalette.ColorRole.WindowText,
    )
    disabled_text = palette.color(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
    )

    assert disabled_text != enabled_text


def test_apply_theme_to_widget_sets_palette(
    qapp,
) -> None:
    theme = create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )
    widget = QWidget()

    apply_theme_to_widget(
        widget,
        theme,
    )

    assert widget.autoFillBackground() is True
    assert (
        widget.palette().color(
            QPalette.ColorRole.Window,
        ).name().upper()
        == theme.colors.background
    )


def test_apply_theme_to_widget_rejects_non_widget(
    qapp,
) -> None:
    theme = create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )

    with pytest.raises(
        TypeError,
        match="Themed target must be QWidget",
    ):
        apply_theme_to_widget(
            object(),  # type: ignore[arg-type]
            theme,
        )


def test_build_palette_sets_placeholder_text_from_syntax_comment(
    qapp,
) -> None:
    theme = create_builtin_theme_registry().get(
        DARK_THEME_ID,
    )

    palette = build_palette(
        theme,
    )

    assert (
        palette.color(
            QPalette.ColorRole.PlaceholderText,
        ).name().upper()
        == theme.colors.syntax_comment
    )


@pytest.mark.parametrize(
    "theme_id",
    (
        LIGHT_THEME_ID,
        DARK_THEME_ID,
        HIGH_CONTRAST_LIGHT_THEME_ID,
        HIGH_CONTRAST_DARK_THEME_ID,
    ),
)
def test_placeholder_text_has_real_contrast_against_base_in_every_builtin_theme(
    qapp,
    theme_id: str,
) -> None:
    # Editor §UIShell-4: a fresh `QPalette()`'s own PlaceholderText
    # default is pure black regardless of theme -- High Contrast Dark
    # resolved it to be literally identical to Text (1.00:1 contrast,
    # 100% invisible) and Dark fell to 1.26:1, catastrophically below
    # WCAG's 3:1 minimum for UI text.
    theme = create_builtin_theme_registry().get(
        theme_id,
    )

    palette = build_palette(
        theme,
    )
    base = palette.color(
        QPalette.ColorRole.Base,
    )
    placeholder = palette.color(
        QPalette.ColorRole.PlaceholderText,
    )

    assert placeholder != base
    assert (
        _wcag_contrast(
            base,
            placeholder,
        )
        >= 3.0
    )


def test_build_palette_rejects_non_theme(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match="Theme must be Theme",
    ):
        build_palette(
            object(),  # type: ignore[arg-type]
        )
