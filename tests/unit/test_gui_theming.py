"""Unit tests for GUI theme palette application."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QWidget

from opencobol2.gui.theming import (
    apply_theme_to_widget,
    build_palette,
)
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
)


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
