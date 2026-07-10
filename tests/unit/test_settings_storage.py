"""Unit tests for OpenCobol2 settings persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import opencobol2.settings.storage as settings_storage
from opencobol2.compiler import CobolSourceFormat
from opencobol2.settings import (
    ApplicationSettings,
    CobolGuideSettings,
    CobolSettings,
    EditorSettings,
    SettingsFormatError,
    SettingsStorage,
    ToolchainSettings,
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

    settings = ApplicationSettings(
        toolchains=ToolchainSettings(
            gnucobol_compiler_path=(
                "C:/custom/gnucobol/bin/cobc.exe"
            ),
            git_executable_path=(
                "C:/custom/git/bin/git.exe"
            ),
            environment_overrides={
                "COB_CONFIG_DIR": (
                    "C:/custom/gnucobol/config"
                ),
                "COB_COPY_DIR": (
                    "C:/custom/gnucobol/copy"
                ),
            },
        ),
        editor=EditorSettings(
            font_family="Cascadia Mono",
            font_size=14,
            tab_width=8,
            insert_spaces=False,
            automatic_indentation=False,
            indentation_width=6,
            code_folding=False,
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
    )

    saved_path = storage.save(
        settings,
    )

    loaded_settings = storage.load()

    assert saved_path == settings_path
    assert loaded_settings == settings
    assert (
        loaded_settings
        .toolchains
        .gnucobol_compiler_path
        == Path(
            "C:/custom/gnucobol/bin/cobc.exe"
        )
    )
    assert (
        loaded_settings.editor.font_family
        == "Cascadia Mono"
    )
    assert (
        loaded_settings.cobol.default_source_format
        is CobolSourceFormat.FREE
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

    assert raw_settings[
        "schema_version"
    ] == 1


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
    assert settings.toolchains == ToolchainSettings()
    assert settings.cobol == CobolSettings()


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

    assert settings_path.read_bytes() == original_payload

    assert tuple(
        tmp_path.glob(
            f".{settings_path.name}.*.tmp"
        )
    ) == ()