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
    """Build a QPalette reflecting one OpenCobol2 theme.

    Per Editor §UIShell-4, `QPalette.ColorRole.PlaceholderText` is set
    explicitly here because it was never set before: every widget that
    relies on `setPlaceholderText()` (Terminal, Watch, Memory, Git
    Changes, Command Palette, Compiler Profiles dialog) rendered a
    fresh `QPalette()`'s built-in default -- pure black regardless of
    theme -- rather than anything sourced from the active theme at all.
    `syntax_comment` is used for it because every built-in theme already
    tunes that color to be legible-but-secondary against
    `editor_background` (the same color `Base` uses here), which is
    exactly the contrast placeholder text needs; computed WCAG contrast
    against `editor_background` is 5.0-11.5:1 across all four built-in
    themes.

    Bevel/border tones for dock-widget separators, splitter handles, and
    sunken/raised frames are derived from the window color relative to
    itself (lighter/darker) rather than from new `ThemeColors` fields, so
    borders show up with real contrast under every theme -- dark or
    light -- without per-theme tuning. Without this, Qt's default
    `QPalette` would leave them at its own built-in light-gray tones,
    which is why panels used to blend together with no visible
    separation.

    The disabled-text color is computed by blending the foreground
    toward the background rather than using alpha, because a single-arg
    `setColor()` call applies to every color group uniformly: without an
    explicit, distinct disabled color, a disabled menu command would
    otherwise render in the exact same, fully legible color as an
    enabled one, and text rendering doesn't reliably respect a
    translucent `QColor` everywhere.

    :param theme: The theme whose colors populate the palette.
    :returns: A new :class:`QPalette` reflecting `theme`.
    :raises TypeError: If `theme` is not a :class:`Theme`.
    """

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
        (
            QPalette.ColorRole.ToolTipBase,
            colors.background,
        ),
        (
            QPalette.ColorRole.ToolTipText,
            colors.foreground,
        ),
        (
            # Editor §UIShell-4: never set before, so every widget that
            # relies on `setPlaceholderText()` (Terminal, Watch, Memory,
            # Git Changes, Command Palette, Compiler Profiles dialog)
            # rendered a fresh `QPalette()`'s built-in default -- pure
            # black regardless of theme -- rather than anything sourced
            # from this theme at all. `syntax_comment` is already tuned
            # by every built-in theme to be legible-but-secondary
            # against `editor_background` (the same color `Base` uses
            # here), which is exactly the contrast placeholder text
            # needs; computed WCAG contrast against `editor_background`
            # is 5.0-11.5:1 across all four built-in themes.
            QPalette.ColorRole.PlaceholderText,
            colors.syntax_comment,
        ),
    )

    for role, hex_color in role_colors:
        palette.setColor(
            role,
            QColor(
                hex_color,
            ),
        )

    # Bevel/border tones for dock-widget separators, splitter handles, and
    # sunken/raised frames. Derived from the window color relative to
    # itself (lighter/darker) rather than new ThemeColors fields, so
    # borders show up with real contrast under every theme -- dark or
    # light -- without per-theme tuning. Without these, Qt's default
    # QPalette leaves them at its own built-in light-gray tones, which is
    # why panels blended together with no visible separation before.
    window_color = QColor(
        colors.background,
    )
    bevel_role_adjustments = (
        (QPalette.ColorRole.Light, 150, True),
        (QPalette.ColorRole.Midlight, 120, True),
        (QPalette.ColorRole.Dark, 150, False),
        (QPalette.ColorRole.Mid, 120, False),
        (QPalette.ColorRole.Shadow, 200, False),
    )

    for role, factor, lighten in bevel_role_adjustments:
        palette.setColor(
            role,
            window_color.lighter(
                factor,
            )
            if lighten
            else window_color.darker(
                factor,
            ),
        )

    # A single-arg setColor() call applies to every color group
    # uniformly, so without this a disabled menu command would render in
    # the exact same (fully legible) color as an enabled one -- blend
    # foreground toward background instead of using alpha, since text
    # rendering doesn't reliably respect a translucent QColor everywhere.
    disabled_text_color = _blend(
        QColor(
            colors.foreground,
        ),
        window_color,
        0.5,
    )

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            role,
            disabled_text_color,
        )

    return palette


def _blend(
    color_a: QColor,
    color_b: QColor,
    ratio: float,
) -> QColor:
    """Blend two opaque colors; `ratio` is how much of `color_a` to keep."""

    return QColor(
        round(
            color_a.red() * ratio
            + color_b.red() * (1 - ratio)
        ),
        round(
            color_a.green() * ratio
            + color_b.green() * (1 - ratio)
        ),
        round(
            color_a.blue() * ratio
            + color_b.blue() * (1 - ratio)
        ),
    )


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
