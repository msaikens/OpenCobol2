"""Domain models for the OpenCobol2 color theme system."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re


_HEX_COLOR_PATTERN = re.compile(
    r"^#[0-9A-Fa-f]{6}$",
)

_COLOR_FIELD_NAMES = (
    "background",
    "foreground",
    "accent",
    "selection_background",
    "selection_foreground",
    "editor_background",
    "editor_foreground",
    "line_number_foreground",
    "current_line_highlight",
    "diagnostic_error",
    "diagnostic_warning",
    "diagnostic_information",
)


class ThemeKind(StrEnum):
    """Supported color-theme categories."""

    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST_LIGHT = "high_contrast_light"
    HIGH_CONTRAST_DARK = "high_contrast_dark"


@dataclass(frozen=True, slots=True, kw_only=True)
class ThemeColors:
    """The named color roles a rendered theme must define."""

    background: str
    foreground: str
    accent: str
    selection_background: str
    selection_foreground: str
    editor_background: str
    editor_foreground: str
    line_number_foreground: str
    current_line_highlight: str
    diagnostic_error: str
    diagnostic_warning: str
    diagnostic_information: str

    def __post_init__(self) -> None:
        """Validate and normalize every color role."""

        for field_name in _COLOR_FIELD_NAMES:
            object.__setattr__(
                self,
                field_name,
                _require_hex_color(
                    getattr(
                        self,
                        field_name,
                    ),
                    f"Theme color {field_name!r}",
                ),
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Theme:
    """One complete, selectable IDE color theme."""

    theme_id: str
    display_name: str
    kind: ThemeKind
    colors: ThemeColors

    def __post_init__(self) -> None:
        """Validate theme identity and structure."""

        object.__setattr__(
            self,
            "theme_id",
            _require_non_empty_string(
                self.theme_id,
                "Theme ID",
            ),
        )

        object.__setattr__(
            self,
            "display_name",
            _require_non_empty_string(
                self.display_name,
                "Theme display name",
            ),
        )

        object.__setattr__(
            self,
            "kind",
            ThemeKind(
                self.kind,
            ),
        )

        if not isinstance(
            self.colors,
            ThemeColors,
        ):
            raise TypeError(
                "Theme colors must be ThemeColors."
            )


def _require_hex_color(
    value: str,
    name: str,
) -> str:
    """Require and normalize an RGB hexadecimal color value."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value = value.strip()

    if not _HEX_COLOR_PATTERN.fullmatch(
        normalized_value,
    ):
        raise ValueError(
            f"{name} must use #RRGGBB format."
        )

    return normalized_value.upper()


def _require_non_empty_string(
    value: str,
    name: str,
) -> str:
    """Require and normalize one non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized_value
