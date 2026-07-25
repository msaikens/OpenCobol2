"""Unit tests for OpenCobol2 settings persistence."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

import opencobol2.settings.storage as settings_storage
from opencobol2.compiler import CobolSourceFormat
from opencobol2.compiler.providers import CompilerProfile
from opencobol2.settings import (
    ApplicationSettings,
    CobolGuideSettings,
    CobolSettings,
    CompilerSettings,
    EditorSettings,
    ExternalToolSettings,
    RecentProjectsSettings,
    SettingsFormatError,
    SettingsStorage,
    ThemeSettings,
    UnsupportedSettingsVersionError,
)


def test_missing_settings_file_returns_defaults(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    settings = storage.load()

    assert settings == ApplicationSettings()


def test_settings_round_trip_preserves_custom_configuration(
    tmp_path: Path,
) -> None:
    settings_path = (
        tmp_path
        / "config"
        / "settings.json"
    )
    storage = SettingsStorage(
        settings_path,
    )

    profile = CompilerProfile(
        provider_id="example.compiler",
        display_name="Custom COBOL",
        configuration={
            "compiler_path": (
                "C:/custom/cobol/bin/compiler.exe"
            ),
            "copybook_paths": (
                "C:/copybooks/common",
                "C:/copybooks/project",
            ),
        },
        environment_overrides={
            "COBOL_HOME": "C:/custom/cobol",
        },
    )

    settings = ApplicationSettings(
        compilers=CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(
                profile,
            ),
        ),
        external_tools=ExternalToolSettings(
            git_executable_path=(
                "C:/custom/git/bin/git.exe"
            ),
        ),
        editor=EditorSettings(
            font_family="Cascadia Mono",
            font_size=14,
            tab_width=8,
            insert_spaces=False,
            automatic_indentation=False,
            indentation_width=6,
            code_folding=False,
            show_minimap=False,
            autosave_enabled=True,
            autosave_interval_seconds=45,
        ),
        cobol=CobolSettings(
            default_source_format=(
                CobolSourceFormat.FREE
            ),
            guides=CobolGuideSettings(
                show_sequence_area=False,
                show_indicator_column=False,
                show_area_a=True,
                show_area_b_boundary=True,
                show_reference_area=False,
                shade_areas=False,
            ),
        ),
        theme=ThemeSettings(
            active_theme_id="light",
        ),
        recent_projects=RecentProjectsSettings(
            paths=(
                Path(
                    "C:/projects/demo.json",
                ),
            ),
        ),
    )

    saved_path = storage.save(
        settings,
    )
    loaded_settings = storage.load()

    assert saved_path == settings_path
    assert loaded_settings == settings
    assert (
        loaded_settings
        .compilers
        .default_profile
        is not None
    )
    assert (
        loaded_settings
        .compilers
        .default_profile
        .provider_id
        == "example.compiler"
    )
    assert (
        loaded_settings
        .external_tools
        .git_executable_path
        == Path(
            "C:/custom/git/bin/git.exe"
        )
    )
    assert (
        loaded_settings.editor.font_family
        == "Cascadia Mono"
    )
    assert (
        loaded_settings.editor.show_minimap
        is False
    )
    assert (
        loaded_settings.editor.autosave_enabled
        is True
    )
    assert (
        loaded_settings
        .editor
        .autosave_interval_seconds
        == 45
    )
    assert (
        loaded_settings
        .cobol
        .default_source_format
        is CobolSourceFormat.FREE
    )
    assert (
        loaded_settings.theme.active_theme_id
        == "light"
    )
    assert (
        loaded_settings.recent_projects.paths
        == (
            Path(
                "C:/projects/demo.json",
            ),
        )
    )


def test_compiler_profile_nested_json_value_round_trip(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    storage = SettingsStorage(
        settings_path,
    )

    profile = CompilerProfile(
        provider_id="plugin.example.remote",
        display_name="Remote Compiler",
        configuration={
            "string": "value",
            "integer": 42,
            "number": 3.5,
            "boolean": True,
            "nothing": None,
            "list": (
                "one",
                2,
                False,
                {
                    "nested": (
                        "a",
                        "b",
                    ),
                },
            ),
            "object": {
                "inner": {
                    "enabled": True,
                },
            },
        },
    )

    settings = ApplicationSettings(
        compilers=CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(
                profile,
            ),
        ),
    )

    storage.save(
        settings,
    )
    loaded = storage.load()

    loaded_profile = (
        loaded.compilers.default_profile
    )

    assert loaded_profile is not None
    assert (
        loaded_profile.configuration
        == profile.configuration
    )
    assert isinstance(
        loaded_profile.configuration["list"],
        tuple,
    )


def test_saved_compiler_profile_json_uses_arrays_and_objects(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    storage = SettingsStorage(
        settings_path,
    )

    profile = CompilerProfile(
        provider_id="example.compiler",
        display_name="Example",
        configuration={
            "arguments": (
                "-x",
                "-Wall",
            ),
            "nested": {
                "enabled": True,
            },
        },
    )

    storage.save(
        ApplicationSettings(
            compilers=CompilerSettings(
                default_profile_id=profile.profile_id,
                profiles=(
                    profile,
                ),
            ),
        )
    )

    raw_settings = json.loads(
        settings_path.read_text(
            encoding="utf-8",
        )
    )
    raw_profile = (
        raw_settings["compilers"]["profiles"][0]
    )

    assert raw_profile["configuration"]["arguments"] == [
        "-x",
        "-Wall",
    ]
    assert raw_profile["configuration"]["nested"] == {
        "enabled": True,
    }


def test_external_git_path_is_persisted(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    storage = SettingsStorage(
        settings_path,
    )

    storage.save(
        ApplicationSettings(
            external_tools=ExternalToolSettings(
                git_executable_path="tools/git.exe",
            ),
        )
    )

    loaded = storage.load()

    assert (
        loaded.external_tools.git_executable_path
        == Path("tools/git.exe")
    )


def test_save_creates_parent_directory(
    tmp_path: Path,
) -> None:
    settings_path = (
        tmp_path
        / "deep"
        / "config"
        / "settings.json"
    )
    storage = SettingsStorage(
        settings_path,
    )

    storage.save(
        ApplicationSettings(),
    )

    assert settings_path.is_file()


def test_saved_json_contains_schema_version(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    storage = SettingsStorage(
        settings_path,
    )

    storage.save(
        ApplicationSettings(),
    )

    raw_settings = json.loads(
        settings_path.read_text(
            encoding="utf-8",
        )
    )

    assert raw_settings["schema_version"] == 1


def test_saved_json_uses_compiler_and_external_tool_groups(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    storage = SettingsStorage(
        settings_path,
    )

    storage.save(
        ApplicationSettings(),
    )

    raw_settings = json.loads(
        settings_path.read_text(
            encoding="utf-8",
        )
    )

    assert "compilers" in raw_settings
    assert "external_tools" in raw_settings
    assert "theme" in raw_settings
    assert "recent_projects" in raw_settings
    assert "toolchains" not in raw_settings


def test_partial_settings_file_uses_current_defaults(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "editor": {
                    "font_size": 16,
                },
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    settings = storage.load()

    assert settings.editor.font_size == 16
    assert settings.editor.tab_width == 4
    assert settings.editor.code_folding is True
    assert settings.compilers == CompilerSettings()
    assert (
        settings.external_tools
        == ExternalToolSettings()
    )
    assert settings.cobol == CobolSettings()
    assert settings.theme == ThemeSettings()
    assert (
        settings.recent_projects
        == RecentProjectsSettings()
    )


def test_compiler_profile_uuid_round_trip(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    storage = SettingsStorage(
        settings_path,
    )

    profile_id = uuid4()
    profile = CompilerProfile(
        profile_id=profile_id,
        provider_id="example.compiler",
        display_name="Example",
    )

    storage.save(
        ApplicationSettings(
            compilers=CompilerSettings(
                default_profile_id=profile_id,
                profiles=(
                    profile,
                ),
            ),
        )
    )

    loaded = storage.load()

    assert (
        loaded.compilers.default_profile_id
        == profile_id
    )
    assert (
        loaded.compilers.profiles[0].profile_id
        == profile_id
    )


def test_invalid_profile_uuid_is_rejected(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "compilers": {
                    "default_profile_id": None,
                    "profiles": [
                        {
                            "profile_id": "not-a-uuid",
                            "provider_id": "example.compiler",
                            "display_name": "Example",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    with pytest.raises(
        SettingsFormatError,
        match="Compiler profile ID must be a valid UUID",
    ):
        storage.load()


def test_duplicate_profile_ids_are_settings_format_error(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    profile_id = str(
        uuid4(),
    )

    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "compilers": {
                    "default_profile_id": profile_id,
                    "profiles": [
                        {
                            "profile_id": profile_id,
                            "provider_id": "example.first",
                            "display_name": "First",
                        },
                        {
                            "profile_id": profile_id,
                            "provider_id": "example.second",
                            "display_name": "Second",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    with pytest.raises(
        SettingsFormatError,
        match="Compiler profile IDs must be unique",
    ):
        storage.load()


def test_invalid_default_profile_reference_is_settings_format_error(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"

    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "compilers": {
                    "default_profile_id": str(
                        uuid4(),
                    ),
                    "profiles": [],
                },
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    with pytest.raises(
        SettingsFormatError,
        match=(
            "Default compiler profile ID must reference "
            "an existing compiler profile"
        ),
    ):
        storage.load()


def test_custom_profiles_without_default_profile_id_loads_with_none(
    tmp_path: Path,
) -> None:
    """Custom profiles with no explicit default_profile_id must not
    fall back to the bundled default profile's UUID -- that UUID
    doesn't name any of these custom profiles, so CompilerSettings
    would reject it and the whole file would fail to load."""

    settings_path = tmp_path / "settings.json"
    profile_id = str(
        uuid4(),
    )

    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "compilers": {
                    "profiles": [
                        {
                            "profile_id": profile_id,
                            "provider_id": "example.compiler",
                            "display_name": "Example",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    loaded = storage.load()

    assert loaded.compilers.default_profile_id is None
    assert len(loaded.compilers.profiles) == 1
    assert (
        str(loaded.compilers.profiles[0].profile_id)
        == profile_id
    )


def test_obsolete_toolchain_layout_is_rejected(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"

    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "toolchains": {
                    "gnucobol_compiler_path": (
                        "C:/old/cobc.exe"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    with pytest.raises(
        SettingsFormatError,
        match="obsolete 'toolchains' layout",
    ):
        storage.load()


def test_invalid_json_is_rejected(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        "{not-json",
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    with pytest.raises(
        SettingsFormatError,
        match="invalid JSON",
    ):
        storage.load()


def test_unsupported_schema_version_is_rejected(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 99,
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    with pytest.raises(
        UnsupportedSettingsVersionError,
        match="Unsupported settings schema version",
    ):
        storage.load()


def test_invalid_setting_type_is_rejected(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "editor": {
                    "code_folding": "yes",
                },
            }
        ),
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    with pytest.raises(
        SettingsFormatError,
        match="Code folding must be a boolean",
    ):
        storage.load()


def test_failed_replace_preserves_existing_settings_and_cleans_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.json"
    original_settings = ApplicationSettings(
        editor=EditorSettings(
            font_size=12,
        ),
    )
    storage = SettingsStorage(
        settings_path,
    )
    storage.save(
        original_settings,
    )
    original_payload = settings_path.read_bytes()

    def fail_replace(
        source: Path,
        destination: Path,
    ) -> None:
        raise PermissionError(
            "replacement denied",
        )

    monkeypatch.setattr(
        settings_storage.os,
        "replace",
        fail_replace,
    )

    changed_settings = ApplicationSettings(
        editor=EditorSettings(
            font_size=18,
        ),
    )

    with pytest.raises(
        PermissionError,
        match="replacement denied",
    ):
        storage.save(
            changed_settings,
        )

    assert (
        settings_path.read_bytes()
        == original_payload
    )
    assert tuple(
        tmp_path.glob(
            f".{settings_path.name}.*.tmp"
        )
    ) == ()