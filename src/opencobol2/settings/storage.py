"""JSON persistence for OpenCobol2 application settings."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from platformdirs import user_config_path

from opencobol2.compiler import CobolSourceFormat
from opencobol2.settings.models import (
    ApplicationSettings,
    CobolGuideSettings,
    CobolSettings,
    CURRENT_SETTINGS_SCHEMA_VERSION,
    EditorSettings,
    ToolchainSettings,
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
            serialized_settings
            + "\n"
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
        "toolchains": {
            "gnucobol_compiler_path": (
                str(
                    settings.toolchains.gnucobol_compiler_path
                )
                if (
                    settings.toolchains.gnucobol_compiler_path
                    is not None
                )
                else None
            ),
            "git_executable_path": (
                str(
                    settings.toolchains.git_executable_path
                )
                if (
                    settings.toolchains.git_executable_path
                    is not None
                )
                else None
            ),
            "environment_overrides": dict(
                sorted(
                    settings.toolchains
                    .environment_overrides
                    .items()
                )
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
        },
        "cobol": {
            "default_source_format": (
                settings.cobol.default_source_format.value
            ),
            "guides": {
                "show_sequence_area": (
                    settings.cobol.guides.show_sequence_area
                ),
                "show_indicator_column": (
                    settings.cobol.guides.show_indicator_column
                ),
                "show_area_a": (
                    settings.cobol.guides.show_area_a
                ),
                "show_area_b_boundary": (
                    settings.cobol.guides.show_area_b_boundary
                ),
                "show_reference_area": (
                    settings.cobol.guides.show_reference_area
                ),
                "shade_areas": (
                    settings.cobol.guides.shade_areas
                ),
            },
        },
    }


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

    toolchains = _decode_toolchain_settings(
        root.get(
            "toolchains",
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

    return ApplicationSettings(
        schema_version=schema_version,
        toolchains=toolchains,
        editor=editor,
        cobol=cobol,
    )


def _decode_toolchain_settings(
    raw_settings: Any,
) -> ToolchainSettings:
    """Decode toolchain settings."""
    settings = _require_mapping(
        raw_settings,
        "Toolchain settings",
    )

    return ToolchainSettings(
        gnucobol_compiler_path=_optional_string(
            settings.get(
                "gnucobol_compiler_path",
            ),
            "GnuCOBOL compiler path",
        ),
        git_executable_path=_optional_string(
            settings.get(
                "git_executable_path",
            ),
            "Git executable path",
        ),
        environment_overrides=_require_string_mapping(
            settings.get(
                "environment_overrides",
                {},
            ),
            "Environment overrides",
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

        result[
            key
        ] = item_value

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