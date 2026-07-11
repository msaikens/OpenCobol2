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
