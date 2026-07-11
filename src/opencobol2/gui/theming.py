"""Applies an OpenCobol2 color theme to Qt widgets."""

from __future__ import annotations

from PySide6.QtGui import (
    QColor,
    QPalette,
)
from PySide6.QtWidgets import QWidget

from opencobol2.theming import Theme


def build_palette(
    theme: Theme,
) -> QPalette:
    """Build a QPalette reflecting one OpenCobol2 theme."""

    if not isinstance(
        theme,
        Theme,
    ):
        raise TypeError(
            "Theme must be Theme."
        )

    colors = theme.colors
    palette = QPalette()

    role_colors = (
        (
            QPalette.ColorRole.Window,
            colors.background,
        ),
        (
            QPalette.ColorRole.WindowText,
            colors.foreground,
        ),
        (
            QPalette.ColorRole.Base,
            colors.editor_background,
        ),
        (
            QPalette.ColorRole.Text,
            colors.editor_foreground,
        ),
        (
            QPalette.ColorRole.Highlight,
            colors.selection_background,
        ),
        (
            QPalette.ColorRole.HighlightedText,
            colors.selection_foreground,
        ),
        (
            QPalette.ColorRole.Button,
            colors.background,
        ),
        (
            QPalette.ColorRole.ButtonText,
            colors.foreground,
        ),
        (
            QPalette.ColorRole.Link,
            colors.accent,
        ),
    )

    for role, hex_color in role_colors:
        palette.setColor(
            role,
            QColor(
                hex_color,
            ),
        )

    return palette


def apply_theme_to_widget(
    widget: QWidget,
    theme: Theme,
) -> None:
    """Apply one OpenCobol2 theme's palette to a widget."""

    if not isinstance(
        widget,
        QWidget,
    ):
        raise TypeError(
            "Themed target must be QWidget."
        )

    widget.setPalette(
        build_palette(
            theme,
        )
    )
    widget.setAutoFillBackground(
        True,
    )
