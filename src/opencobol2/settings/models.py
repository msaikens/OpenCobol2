"""Typed application settings models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from opencobol2.compiler import CobolSourceFormat


CURRENT_SETTINGS_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolchainSettings:
    """User-configurable external tool and environment settings."""

    gnucobol_compiler_path: Path | None = None
    git_executable_path: Path | None = None
    environment_overrides: Mapping[str, str] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        """Normalize toolchain configuration."""
        object.__setattr__(
            self,
            "gnucobol_compiler_path",
            _normalize_optional_path(
                self.gnucobol_compiler_path,
            ),
        )

        object.__setattr__(
            self,
            "git_executable_path",
            _normalize_optional_path(
                self.git_executable_path,
            ),
        )

        normalized_environment = (
            _normalize_environment_overrides(
                self.environment_overrides,
            )
        )

        object.__setattr__(
            self,
            "environment_overrides",
            MappingProxyType(
                normalized_environment,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EditorSettings:
    """General text editor behavior settings."""

    font_family: str = ""
    font_size: int = 11
    tab_width: int = 4
    insert_spaces: bool = True
    automatic_indentation: bool = True
    indentation_width: int = 4
    code_folding: bool = True

    def __post_init__(self) -> None:
        """Validate editor settings."""
        if not isinstance(
            self.font_family,
            str,
        ):
            raise TypeError(
                "Editor font family must be a string."
            )

        normalized_font_family = (
            self.font_family.strip()
        )

        object.__setattr__(
            self,
            "font_family",
            normalized_font_family,
        )

        _require_positive_integer(
            self.font_size,
            "Editor font size",
        )

        _require_positive_integer(
            self.tab_width,
            "Editor tab width",
        )

        _require_boolean(
            self.insert_spaces,
            "Insert spaces",
        )

        _require_boolean(
            self.automatic_indentation,
            "Automatic indentation",
        )

        _require_positive_integer(
            self.indentation_width,
            "Editor indentation width",
        )

        _require_boolean(
            self.code_folding,
            "Code folding",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CobolGuideSettings:
    """Visibility settings for COBOL reference-format guides."""

    show_sequence_area: bool = True
    show_indicator_column: bool = True
    show_area_a: bool = True
    show_area_b_boundary: bool = True
    show_reference_area: bool = True
    shade_areas: bool = True

    def __post_init__(self) -> None:
        """Validate guide visibility settings."""
        _require_boolean(
            self.show_sequence_area,
            "Sequence area visibility",
        )

        _require_boolean(
            self.show_indicator_column,
            "Indicator column visibility",
        )

        _require_boolean(
            self.show_area_a,
            "Area A visibility",
        )

        _require_boolean(
            self.show_area_b_boundary,
            "Area B boundary visibility",
        )

        _require_boolean(
            self.show_reference_area,
            "Reference area visibility",
        )

        _require_boolean(
            self.shade_areas,
            "COBOL area shading",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CobolSettings:
    """COBOL language and editor preference settings."""

    default_source_format: CobolSourceFormat = (
        CobolSourceFormat.FIXED
    )
    guides: CobolGuideSettings = field(
        default_factory=CobolGuideSettings,
    )

    def __post_init__(self) -> None:
        """Normalize COBOL settings."""
        object.__setattr__(
            self,
            "default_source_format",
            CobolSourceFormat(
                self.default_source_format,
            ),
        )

        if not isinstance(
            self.guides,
            CobolGuideSettings,
        ):
            raise TypeError(
                "COBOL guides must be CobolGuideSettings."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplicationSettings:
    """Complete persisted OpenCobol2 settings state."""

    schema_version: int = CURRENT_SETTINGS_SCHEMA_VERSION
    toolchains: ToolchainSettings = field(
        default_factory=ToolchainSettings,
    )
    editor: EditorSettings = field(
        default_factory=EditorSettings,
    )
    cobol: CobolSettings = field(
        default_factory=CobolSettings,
    )

    def __post_init__(self) -> None:
        """Validate application settings."""
        if (
            not isinstance(
                self.schema_version,
                int,
            )
            or isinstance(
                self.schema_version,
                bool,
            )
        ):
            raise TypeError(
                "Settings schema version must be an integer."
            )

        if self.schema_version <= 0:
            raise ValueError(
                "Settings schema version must be positive."
            )

        if not isinstance(
            self.toolchains,
            ToolchainSettings,
        ):
            raise TypeError(
                "Toolchain settings must be ToolchainSettings."
            )

        if not isinstance(
            self.editor,
            EditorSettings,
        ):
            raise TypeError(
                "Editor settings must be EditorSettings."
            )

        if not isinstance(
            self.cobol,
            CobolSettings,
        ):
            raise TypeError(
                "COBOL settings must be CobolSettings."
            )


def _normalize_optional_path(
    path: Path | str | None,
) -> Path | None:
    """Normalize an optional filesystem path."""
    if path is None:
        return None

    return Path(
        path,
    )


def _normalize_environment_overrides(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Validate and copy external-process environment overrides."""
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "Environment overrides must be a mapping."
        )

    normalized_environment: dict[
        str,
        str,
    ] = {}

    for name, value in environment.items():
        if not isinstance(
            name,
            str,
        ):
            raise TypeError(
                "Environment variable names must be strings."
            )

        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError(
                "Environment variable names must not be empty."
            )

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "Environment variable values must be strings."
            )

        normalized_environment[
            normalized_name
        ] = value

    return normalized_environment


def _require_positive_integer(
    value: int,
    name: str,
) -> None:
    """Require a positive non-boolean integer setting."""
    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
    ):
        raise TypeError(
            f"{name} must be an integer."
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be positive."
        )


def _require_boolean(
    value: bool,
    name: str,
) -> None:
    """Require a real boolean setting value."""
    if not isinstance(
        value,
        bool,
    ):
        raise TypeError(
            f"{name} must be a boolean."
        )