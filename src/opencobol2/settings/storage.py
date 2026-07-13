"""JSON persistence for OpenCobol2 application settings."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from uuid import UUID

from platformdirs import user_config_path

from opencobol2.compiler import CobolSourceFormat
from opencobol2.compiler.providers import (
    CompilerProfile,
    JsonValue,
)
from opencobol2.settings.models import (
    ApplicationSettings,
    CobolGuideSettings,
    CobolSettings,
    CompilerSettings,
    CURRENT_SETTINGS_SCHEMA_VERSION,
    EditorSettings,
    ExternalToolSettings,
    RecentProjectsSettings,
    ThemeSettings,
)


_SETTINGS_FILENAME = "settings.json"


class SettingsFormatError(ValueError):
    """Raised when persisted settings cannot be decoded."""


class UnsupportedSettingsVersionError(
    SettingsFormatError,
):
    """Raised when persisted settings use an unsupported schema."""


def default_settings_path() -> Path:
    """Return the platform-appropriate OpenCobol2 settings path."""
    return (
        user_config_path(
            appname="OpenCobol2",
            appauthor=False,
            ensure_exists=False,
        )
        / _SETTINGS_FILENAME
    )


class SettingsStorage:
    """Loads and saves persisted OpenCobol2 settings."""

    __slots__ = (
        "_path",
    )

    def __init__(
        self,
        path: Path | str | None = None,
    ) -> None:
        self._path = (
            default_settings_path()
            if path is None
            else Path(path)
        )

    @property
    def path(self) -> Path:
        """Return the settings file path."""
        return self._path

    def load(
        self,
    ) -> ApplicationSettings:
        """Load settings or return defaults when no file exists."""
        if not self._path.exists():
            return ApplicationSettings()

        try:
            raw_settings = json.loads(
                self._path.read_text(
                    encoding="utf-8",
                )
            )
        except json.JSONDecodeError as error:
            raise SettingsFormatError(
                "Settings file contains invalid JSON."
            ) from error

        return _decode_settings(
            raw_settings,
        )

    def save(
        self,
        settings: ApplicationSettings,
    ) -> Path:
        """Persist settings through a same-directory replacement file."""
        if not isinstance(
            settings,
            ApplicationSettings,
        ):
            raise TypeError(
                "Settings must be ApplicationSettings."
            )

        serialized_settings = json.dumps(
            _encode_settings(
                settings,
            ),
            ensure_ascii=False,
            indent=2,
        )

        payload = (
            serialized_settings + "\n"
        ).encode(
            "utf-8",
        )

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        _write_replacement_file(
            self._path,
            payload,
        )

        return self._path


def _encode_settings(
    settings: ApplicationSettings,
) -> dict[str, Any]:
    """Encode typed settings into JSON-compatible values."""
    return {
        "schema_version": settings.schema_version,
        "compilers": _encode_compiler_settings(
            settings.compilers,
        ),
        "external_tools": {
            "git_executable_path": (
                str(
                    settings
                    .external_tools
                    .git_executable_path
                )
                if (
                    settings
                    .external_tools
                    .git_executable_path
                    is not None
                )
                else None
            ),
        },
        "editor": {
            "font_family": settings.editor.font_family,
            "font_size": settings.editor.font_size,
            "tab_width": settings.editor.tab_width,
            "insert_spaces": settings.editor.insert_spaces,
            "automatic_indentation": (
                settings.editor.automatic_indentation
            ),
            "indentation_width": (
                settings.editor.indentation_width
            ),
            "code_folding": settings.editor.code_folding,
            "show_minimap": settings.editor.show_minimap,
            "autosave_enabled": (
                settings.editor.autosave_enabled
            ),
            "autosave_interval_seconds": (
                settings.editor.autosave_interval_seconds
            ),
        },
        "cobol": {
            "default_source_format": (
                settings.cobol.default_source_format.value
            ),
            "guides": {
                "show_sequence_area": (
                    settings
                    .cobol
                    .guides
                    .show_sequence_area
                ),
                "show_indicator_column": (
                    settings
                    .cobol
                    .guides
                    .show_indicator_column
                ),
                "show_area_a": (
                    settings.cobol.guides.show_area_a
                ),
                "show_area_b_boundary": (
                    settings
                    .cobol
                    .guides
                    .show_area_b_boundary
                ),
                "show_reference_area": (
                    settings
                    .cobol
                    .guides
                    .show_reference_area
                ),
                "shade_areas": (
                    settings.cobol.guides.shade_areas
                ),
            },
        },
        "theme": {
            "active_theme_id": (
                settings.theme.active_theme_id
            ),
        },
        "recent_projects": {
            "paths": [
                str(path)
                for path in settings.recent_projects.paths
            ],
        },
    }


def _encode_compiler_settings(
    settings: CompilerSettings,
) -> dict[str, Any]:
    """Encode configured compiler profiles."""
    return {
        "default_profile_id": (
            str(
                settings.default_profile_id,
            )
            if settings.default_profile_id is not None
            else None
        ),
        "profiles": [
            _encode_compiler_profile(
                profile,
            )
            for profile in settings.profiles
        ],
    }


def _encode_compiler_profile(
    profile: CompilerProfile,
) -> dict[str, Any]:
    """Encode one persisted compiler profile."""
    return {
        "profile_id": str(
            profile.profile_id,
        ),
        "provider_id": profile.provider_id,
        "display_name": profile.display_name,
        "configuration": {
            key: _encode_json_value(
                value,
            )
            for key, value in sorted(
                profile.configuration.items(),
            )
        },
        "environment_overrides": dict(
            sorted(
                profile.environment_overrides.items(),
            )
        ),
    }


def _encode_json_value(
    value: JsonValue,
) -> Any:
    """Convert a frozen compiler configuration value to JSON data."""
    if isinstance(
        value,
        Mapping,
    ):
        return {
            key: _encode_json_value(
                item_value,
            )
            for key, item_value in sorted(
                value.items(),
            )
        }

    if isinstance(
        value,
        tuple,
    ):
        return [
            _encode_json_value(
                item,
            )
            for item in value
        ]

    return value


def _decode_settings(
    raw_settings: Any,
) -> ApplicationSettings:
    """Decode persisted JSON values into typed settings."""
    root = _require_mapping(
        raw_settings,
        "Settings root",
    )

    schema_version = _require_integer(
        root.get(
            "schema_version",
        ),
        "Settings schema version",
    )

    if (
        schema_version
        != CURRENT_SETTINGS_SCHEMA_VERSION
    ):
        raise UnsupportedSettingsVersionError(
            "Unsupported settings schema version: "
            f"{schema_version}. "
            "Current version is "
            f"{CURRENT_SETTINGS_SCHEMA_VERSION}."
        )

    if "toolchains" in root:
        raise SettingsFormatError(
            "Settings schema version 1 uses the current "
            "'compilers' and 'external_tools' layout; "
            "the obsolete 'toolchains' layout is not supported."
        )

    try:
        compilers = _decode_compiler_settings(
            root.get(
                "compilers",
                {},
            )
        )
        external_tools = _decode_external_tool_settings(
            root.get(
                "external_tools",
                {},
            )
        )
        editor = _decode_editor_settings(
            root.get(
                "editor",
                {},
            )
        )
        cobol = _decode_cobol_settings(
            root.get(
                "cobol",
                {},
            )
        )
        theme = _decode_theme_settings(
            root.get(
                "theme",
                {},
            )
        )
        recent_projects = _decode_recent_projects_settings(
            root.get(
                "recent_projects",
                {},
            )
        )

        return ApplicationSettings(
            schema_version=schema_version,
            compilers=compilers,
            external_tools=external_tools,
            editor=editor,
            cobol=cobol,
            theme=theme,
            recent_projects=recent_projects,
        )
    except SettingsFormatError:
        raise
    except (
        TypeError,
        ValueError,
    ) as error:
        raise SettingsFormatError(
            f"Settings contain an invalid value: {error}"
        ) from error


def _decode_compiler_settings(
    raw_settings: Any,
) -> CompilerSettings:
    """Decode compiler profile settings."""
    settings = _require_mapping(
        raw_settings,
        "Compiler settings",
    )
    defaults = CompilerSettings()

    raw_profiles = settings.get(
        "profiles",
        None,
    )

    if raw_profiles is None:
        profiles = defaults.profiles
    else:
        profile_values = _require_list(
            raw_profiles,
            "Compiler profiles",
        )
        profiles = tuple(
            _decode_compiler_profile(
                raw_profile,
            )
            for raw_profile in profile_values
        )

    raw_default_profile_id = settings.get(
        "default_profile_id",
        (
            str(defaults.default_profile_id)
            if defaults.default_profile_id is not None
            else None
        ),
    )

    default_profile_id = _optional_uuid(
        raw_default_profile_id,
        "Default compiler profile ID",
    )

    return CompilerSettings(
        default_profile_id=default_profile_id,
        profiles=profiles,
    )


def _decode_compiler_profile(
    raw_profile: Any,
) -> CompilerProfile:
    """Decode one persisted compiler profile."""
    profile = _require_mapping(
        raw_profile,
        "Compiler profile",
    )

    profile_id = _require_uuid(
        profile.get(
            "profile_id",
        ),
        "Compiler profile ID",
    )
    provider_id = _require_string(
        profile.get(
            "provider_id",
        ),
        "Compiler provider ID",
    )
    display_name = _require_string(
        profile.get(
            "display_name",
        ),
        "Compiler profile display name",
    )
    configuration = _decode_json_mapping(
        profile.get(
            "configuration",
            {},
        ),
        "Compiler profile configuration",
    )
    environment_overrides = _require_string_mapping(
        profile.get(
            "environment_overrides",
            {},
        ),
        "Compiler environment overrides",
    )

    return CompilerProfile(
        profile_id=profile_id,
        provider_id=provider_id,
        display_name=display_name,
        configuration=configuration,
        environment_overrides=environment_overrides,
    )


def _decode_external_tool_settings(
    raw_settings: Any,
) -> ExternalToolSettings:
    """Decode external application tool settings."""
    settings = _require_mapping(
        raw_settings,
        "External tool settings",
    )

    return ExternalToolSettings(
        git_executable_path=_optional_string(
            settings.get(
                "git_executable_path",
            ),
            "Git executable path",
        ),
    )


def _decode_editor_settings(
    raw_settings: Any,
) -> EditorSettings:
    """Decode general editor settings."""
    settings = _require_mapping(
        raw_settings,
        "Editor settings",
    )
    defaults = EditorSettings()

    return EditorSettings(
        font_family=_require_string(
            settings.get(
                "font_family",
                defaults.font_family,
            ),
            "Editor font family",
        ),
        font_size=_require_integer(
            settings.get(
                "font_size",
                defaults.font_size,
            ),
            "Editor font size",
        ),
        tab_width=_require_integer(
            settings.get(
                "tab_width",
                defaults.tab_width,
            ),
            "Editor tab width",
        ),
        insert_spaces=_require_boolean(
            settings.get(
                "insert_spaces",
                defaults.insert_spaces,
            ),
            "Insert spaces",
        ),
        automatic_indentation=_require_boolean(
            settings.get(
                "automatic_indentation",
                defaults.automatic_indentation,
            ),
            "Automatic indentation",
        ),
        indentation_width=_require_integer(
            settings.get(
                "indentation_width",
                defaults.indentation_width,
            ),
            "Editor indentation width",
        ),
        code_folding=_require_boolean(
            settings.get(
                "code_folding",
                defaults.code_folding,
            ),
            "Code folding",
        ),
        show_minimap=_require_boolean(
            settings.get(
                "show_minimap",
                defaults.show_minimap,
            ),
            "Show minimap",
        ),
        autosave_enabled=_require_boolean(
            settings.get(
                "autosave_enabled",
                defaults.autosave_enabled,
            ),
            "Autosave enabled",
        ),
        autosave_interval_seconds=_require_integer(
            settings.get(
                "autosave_interval_seconds",
                defaults.autosave_interval_seconds,
            ),
            "Autosave interval",
        ),
    )


def _decode_cobol_settings(
    raw_settings: Any,
) -> CobolSettings:
    """Decode COBOL language settings."""
    settings = _require_mapping(
        raw_settings,
        "COBOL settings",
    )
    defaults = CobolSettings()

    raw_source_format = _require_string(
        settings.get(
            "default_source_format",
            defaults.default_source_format.value,
        ),
        "Default COBOL source format",
    )

    try:
        source_format = CobolSourceFormat(
            raw_source_format,
        )
    except ValueError as error:
        raise SettingsFormatError(
            "Unknown default COBOL source format: "
            f"{raw_source_format!r}."
        ) from error

    guides = _decode_cobol_guide_settings(
        settings.get(
            "guides",
            {},
        )
    )

    return CobolSettings(
        default_source_format=source_format,
        guides=guides,
    )


def _decode_cobol_guide_settings(
    raw_settings: Any,
) -> CobolGuideSettings:
    """Decode COBOL reference-guide visibility settings."""
    settings = _require_mapping(
        raw_settings,
        "COBOL guide settings",
    )
    defaults = CobolGuideSettings()

    return CobolGuideSettings(
        show_sequence_area=_require_boolean(
            settings.get(
                "show_sequence_area",
                defaults.show_sequence_area,
            ),
            "Sequence area visibility",
        ),
        show_indicator_column=_require_boolean(
            settings.get(
                "show_indicator_column",
                defaults.show_indicator_column,
            ),
            "Indicator column visibility",
        ),
        show_area_a=_require_boolean(
            settings.get(
                "show_area_a",
                defaults.show_area_a,
            ),
            "Area A visibility",
        ),
        show_area_b_boundary=_require_boolean(
            settings.get(
                "show_area_b_boundary",
                defaults.show_area_b_boundary,
            ),
            "Area B boundary visibility",
        ),
        show_reference_area=_require_boolean(
            settings.get(
                "show_reference_area",
                defaults.show_reference_area,
            ),
            "Reference area visibility",
        ),
        shade_areas=_require_boolean(
            settings.get(
                "shade_areas",
                defaults.shade_areas,
            ),
            "COBOL area shading",
        ),
    )


def _decode_theme_settings(
    raw_settings: Any,
) -> ThemeSettings:
    """Decode selected color-theme settings."""
    settings = _require_mapping(
        raw_settings,
        "Theme settings",
    )
    defaults = ThemeSettings()

    return ThemeSettings(
        active_theme_id=_require_string(
            settings.get(
                "active_theme_id",
                defaults.active_theme_id,
            ),
            "Active theme ID",
        ),
    )


def _decode_recent_projects_settings(
    raw_settings: Any,
) -> RecentProjectsSettings:
    """Decode the recent-project path list."""
    settings = _require_mapping(
        raw_settings,
        "Recent projects settings",
    )
    raw_paths = _require_list(
        settings.get(
            "paths",
            [],
        ),
        "Recent project paths",
    )

    return RecentProjectsSettings(
        paths=tuple(
            Path(
                _require_string(
                    raw_path,
                    "Recent project path",
                ),
            )
            for raw_path in raw_paths
        ),
    )


def _decode_json_mapping(
    value: Any,
    name: str,
) -> dict[str, JsonValue]:
    """Decode a JSON object containing recursive configuration values."""
    mapping = _require_mapping(
        value,
        name,
    )

    result: dict[str, JsonValue] = {}

    for key, item_value in mapping.items():
        if not isinstance(
            key,
            str,
        ):
            raise SettingsFormatError(
                f"{name} keys must be strings."
            )

        result[key] = _decode_json_value(
            item_value,
            f"{name} value for {key!r}",
        )

    return result


def _decode_json_value(
    value: Any,
    name: str,
) -> JsonValue:
    """Decode one recursive JSON-compatible compiler value."""
    if (
        value is None
        or isinstance(
            value,
            (
                str,
                bool,
                int,
            ),
        )
    ):
        return value

    if isinstance(
        value,
        float,
    ):
        return value

    if isinstance(
        value,
        list,
    ):
        return tuple(
            _decode_json_value(
                item,
                f"{name} item",
            )
            for item in value
        )

    if isinstance(
        value,
        Mapping,
    ):
        result: dict[str, JsonValue] = {}

        for key, item_value in value.items():
            if not isinstance(
                key,
                str,
            ):
                raise SettingsFormatError(
                    f"{name} object keys must be strings."
                )

            result[key] = _decode_json_value(
                item_value,
                f"{name} value for {key!r}",
            )

        return result

    raise SettingsFormatError(
        f"{name} contains an unsupported JSON value."
    )


def _write_replacement_file(
    destination: Path,
    payload: bytes,
) -> None:
    """Write a sibling temporary file and replace the destination."""
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(
                temporary_file.name,
            )
            temporary_file.write(
                payload,
            )
            temporary_file.flush()
            os.fsync(
                temporary_file.fileno(),
            )

        os.replace(
            temporary_path,
            destination,
        )
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _require_mapping(
    value: Any,
    name: str,
) -> Mapping[str, Any]:
    """Require a mapping value."""
    if not isinstance(
        value,
        Mapping,
    ):
        raise SettingsFormatError(
            f"{name} must be an object."
        )

    return value


def _require_list(
    value: Any,
    name: str,
) -> list[Any]:
    """Require a JSON array value."""
    if not isinstance(
        value,
        list,
    ):
        raise SettingsFormatError(
            f"{name} must be an array."
        )

    return value


def _require_string_mapping(
    value: Any,
    name: str,
) -> dict[str, str]:
    """Require a mapping containing string keys and values."""
    mapping = _require_mapping(
        value,
        name,
    )

    result: dict[str, str] = {}

    for key, item_value in mapping.items():
        if not isinstance(
            key,
            str,
        ):
            raise SettingsFormatError(
                f"{name} keys must be strings."
            )

        if not isinstance(
            item_value,
            str,
        ):
            raise SettingsFormatError(
                f"{name} values must be strings."
            )

        result[key] = item_value

    return result


def _require_string(
    value: Any,
    name: str,
) -> str:
    """Require a string value."""
    if not isinstance(
        value,
        str,
    ):
        raise SettingsFormatError(
            f"{name} must be a string."
        )

    return value


def _optional_string(
    value: Any,
    name: str,
) -> str | None:
    """Require a string or null value."""
    if value is None:
        return None

    return _require_string(
        value,
        name,
    )


def _require_uuid(
    value: Any,
    name: str,
) -> UUID:
    """Require a valid UUID string."""
    raw_value = _require_string(
        value,
        name,
    )

    try:
        return UUID(
            raw_value,
        )
    except ValueError as error:
        raise SettingsFormatError(
            f"{name} must be a valid UUID."
        ) from error


def _optional_uuid(
    value: Any,
    name: str,
) -> UUID | None:
    """Require a valid UUID string or null."""
    if value is None:
        return None

    return _require_uuid(
        value,
        name,
    )


def _require_integer(
    value: Any,
    name: str,
) -> int:
    """Require a non-boolean integer value."""
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
        raise SettingsFormatError(
            f"{name} must be an integer."
        )

    return value


def _require_boolean(
    value: Any,
    name: str,
) -> bool:
    """Require a boolean value."""
    if not isinstance(
        value,
        bool,
    ):
        raise SettingsFormatError(
            f"{name} must be a boolean."
        )

    return value