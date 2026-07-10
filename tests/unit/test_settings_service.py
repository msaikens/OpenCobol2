"""Unit tests for the application settings service."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.settings import (
    ApplicationSettings,
    CobolSettings,
    EditorSettings,
    SettingsService,
    SettingsStorage,
    ToolchainSettings,
)


def test_service_loads_current_settings_from_storage(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    expected_settings = ApplicationSettings(
        editor=EditorSettings(
            font_size=16,
        ),
    )

    storage.save(
        expected_settings,
    )

    service = SettingsService(
        storage,
    )

    assert service.storage is storage
    assert service.current == expected_settings


def test_apply_persists_and_updates_current_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    service = SettingsService(
        storage,
    )

    settings = ApplicationSettings(
        editor=EditorSettings(
            font_size=18,
        ),
    )

    applied_settings = service.apply(
        settings,
    )

    assert applied_settings is settings
    assert service.current is settings
    assert storage.load() == settings


def test_failed_apply_preserves_current_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    service = SettingsService(
        storage,
    )

    original_settings = service.current

    changed_settings = ApplicationSettings(
        editor=EditorSettings(
            font_size=18,
        ),
    )

    def fail_save(
        self: SettingsStorage,
        settings: ApplicationSettings,
    ) -> Path:
        raise PermissionError(
            "settings write denied",
        )

    monkeypatch.setattr(
        SettingsStorage,
        "save",
        fail_save,
    )

    with pytest.raises(
        PermissionError,
        match="settings write denied",
    ):
        service.apply(
            changed_settings,
        )

    assert service.current is original_settings


def test_update_toolchains_preserves_other_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    service = SettingsService(
        storage,
    )

    original_editor = service.current.editor
    original_cobol = service.current.cobol

    toolchains = ToolchainSettings(
        gnucobol_compiler_path=(
            "C:/custom/gnucobol/bin/cobc.exe"
        ),
    )

    updated_settings = service.update_toolchains(
        toolchains,
    )

    assert updated_settings.toolchains is toolchains
    assert updated_settings.editor is original_editor
    assert updated_settings.cobol is original_cobol
    assert storage.load() == updated_settings


def test_update_editor_preserves_other_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    service = SettingsService(
        storage,
    )

    original_toolchains = service.current.toolchains
    original_cobol = service.current.cobol

    editor = EditorSettings(
        font_family="Cascadia Mono",
        font_size=15,
    )

    updated_settings = service.update_editor(
        editor,
    )

    assert updated_settings.toolchains is original_toolchains
    assert updated_settings.editor is editor
    assert updated_settings.cobol is original_cobol
    assert storage.load() == updated_settings


def test_update_cobol_preserves_other_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    service = SettingsService(
        storage,
    )

    original_toolchains = service.current.toolchains
    original_editor = service.current.editor

    cobol = CobolSettings(
        default_source_format=(
            CobolSourceFormat.FREE
        ),
    )

    updated_settings = service.update_cobol(
        cobol,
    )

    assert updated_settings.toolchains is original_toolchains
    assert updated_settings.editor is original_editor
    assert updated_settings.cobol is cobol
    assert storage.load() == updated_settings


def test_reload_replaces_current_snapshot_from_disk(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )

    service = SettingsService(
        storage,
    )

    external_settings = ApplicationSettings(
        editor=EditorSettings(
            font_size=20,
        ),
    )

    storage.save(
        external_settings,
    )

    reloaded_settings = service.reload()

    assert reloaded_settings == external_settings
    assert service.current == external_settings