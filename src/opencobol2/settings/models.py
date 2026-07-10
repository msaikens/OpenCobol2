"""Typed application settings models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from opencobol2.compiler import CobolSourceFormat
from opencobol2.compiler.providers import (
    CompilerProfile,
    GNUCOBOL_PROVIDER_ID,
)


CURRENT_SETTINGS_SCHEMA_VERSION = 1

DEFAULT_GNUCOBOL_PROFILE_ID = UUID(
    "4ceea39a-11d5-5a22-91e3-cf5318eb3a02"
)


def _create_default_gnucobol_profile() -> CompilerProfile:
    """Create the built-in automatic-discovery GnuCOBOL profile."""
    return CompilerProfile(
        profile_id=DEFAULT_GNUCOBOL_PROFILE_ID,
        provider_id=GNUCOBOL_PROVIDER_ID,
        display_name="GnuCOBOL",
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompilerSettings:
    """Configured compiler profiles and default compiler selection."""

    default_profile_id: UUID | None = (
        DEFAULT_GNUCOBOL_PROFILE_ID
    )
    profiles: tuple[CompilerProfile, ...] = field(
        default_factory=lambda: (
            _create_default_gnucobol_profile(),
        ),
    )

    def __post_init__(self) -> None:
        """Validate and normalize compiler profile settings."""
        if (
            self.default_profile_id is not None
            and not isinstance(
                self.default_profile_id,
                UUID,
            )
        ):
            raise TypeError(
                "Default compiler profile ID must be a UUID or None."
            )

        profiles = tuple(
            self.profiles,
        )

        if not all(
            isinstance(
                profile,
                CompilerProfile,
            )
            for profile in profiles
        ):
            raise TypeError(
                "Compiler profiles must contain "
                "CompilerProfile instances."
            )

        profile_ids = tuple(
            profile.profile_id
            for profile in profiles
        )

        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError(
                "Compiler profile IDs must be unique."
            )

        if (
            self.default_profile_id is not None
            and self.default_profile_id not in profile_ids
        ):
            raise ValueError(
                "Default compiler profile ID must reference "
                "an existing compiler profile."
            )

        object.__setattr__(
            self,
            "profiles",
            profiles,
        )

    @property
    def default_profile(
        self,
    ) -> CompilerProfile | None:
        """Return the selected default compiler profile."""
        if self.default_profile_id is None:
            return None

        return self.get_profile(
            self.default_profile_id,
        )

    def get_profile(
        self,
        profile_id: UUID,
    ) -> CompilerProfile | None:
        """Return a configured compiler profile by ID."""
        if not isinstance(
            profile_id,
            UUID,
        ):
            raise TypeError(
                "Compiler profile ID must be a UUID."
            )

        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile

        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalToolSettings:
    """User-configurable external application tool settings."""

    git_executable_path: Path | None = None

    def __post_init__(self) -> None:
        """Normalize external tool paths."""
        object.__setattr__(
            self,
            "git_executable_path",
            _normalize_optional_path(
                self.git_executable_path,
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
    compilers: CompilerSettings = field(
        default_factory=CompilerSettings,
    )
    external_tools: ExternalToolSettings = field(
        default_factory=ExternalToolSettings,
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
            self.compilers,
            CompilerSettings,
        ):
            raise TypeError(
                "Compiler settings must be CompilerSettings."
            )

        if not isinstance(
            self.external_tools,
            ExternalToolSettings,
        ):
            raise TypeError(
                "External tool settings must be "
                "ExternalToolSettings."
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