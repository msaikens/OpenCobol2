"""Unit tests for the application settings service."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.compiler.providers import (
    CompilerProfile,
)
from opencobol2.settings import (
    ApplicationSettings,
    CobolSettings,
    CompilerSettings,
    EditorSettings,
    ExternalToolSettings,
    RecentProjectsSettings,
    SettingsService,
    SettingsStorage,
    ThemeSettings,
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


def test_service_falls_back_to_defaults_on_corrupt_settings_file(
    tmp_path: Path,
) -> None:
    """A corrupt settings.json must not prevent the app from launching
    at all -- it falls back to defaults and records the failure."""

    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        "{not valid json",
        encoding="utf-8",
    )
    storage = SettingsStorage(
        settings_path,
    )

    service = SettingsService(
        storage,
    )

    assert service.current == ApplicationSettings()
    assert service.load_error is not None


def test_service_has_no_load_error_on_clean_start(
    tmp_path: Path,
) -> None:
    service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )

    assert service.load_error is None


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


def test_update_compilers_preserves_other_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )
    service = SettingsService(
        storage,
    )

    original_external_tools = (
        service.current.external_tools
    )
    original_editor = service.current.editor
    original_cobol = service.current.cobol

    profile = CompilerProfile(
        provider_id="example.compiler",
        display_name="Example Compiler",
    )
    compilers = CompilerSettings(
        default_profile_id=profile.profile_id,
        profiles=(
            profile,
        ),
    )

    updated_settings = service.update_compilers(
        compilers,
    )

    assert updated_settings.compilers is compilers
    assert (
        updated_settings.external_tools
        is original_external_tools
    )
    assert updated_settings.editor is original_editor
    assert updated_settings.cobol is original_cobol
    assert storage.load() == updated_settings


def test_update_external_tools_preserves_other_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )
    service = SettingsService(
        storage,
    )

    original_compilers = service.current.compilers
    original_editor = service.current.editor
    original_cobol = service.current.cobol

    external_tools = ExternalToolSettings(
        git_executable_path=(
            "C:/Program Files/Git/bin/git.exe"
        ),
    )

    updated_settings = (
        service.update_external_tools(
            external_tools,
        )
    )

    assert (
        updated_settings.compilers
        is original_compilers
    )
    assert (
        updated_settings.external_tools
        is external_tools
    )
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

    original_compilers = service.current.compilers
    original_external_tools = (
        service.current.external_tools
    )
    original_cobol = service.current.cobol

    editor = EditorSettings(
        font_family="Cascadia Mono",
        font_size=15,
    )

    updated_settings = service.update_editor(
        editor,
    )

    assert (
        updated_settings.compilers
        is original_compilers
    )
    assert (
        updated_settings.external_tools
        is original_external_tools
    )
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

    original_compilers = service.current.compilers
    original_external_tools = (
        service.current.external_tools
    )
    original_editor = service.current.editor

    cobol = CobolSettings(
        default_source_format=(
            CobolSourceFormat.FREE
        ),
    )

    updated_settings = service.update_cobol(
        cobol,
    )

    assert (
        updated_settings.compilers
        is original_compilers
    )
    assert (
        updated_settings.external_tools
        is original_external_tools
    )
    assert updated_settings.editor is original_editor
    assert updated_settings.cobol is cobol
    assert storage.load() == updated_settings


def test_update_theme_preserves_other_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )
    service = SettingsService(
        storage,
    )

    original_compilers = service.current.compilers
    original_editor = service.current.editor
    original_cobol = service.current.cobol

    theme = ThemeSettings(
        active_theme_id="light",
    )

    updated_settings = service.update_theme(
        theme,
    )

    assert (
        updated_settings.compilers
        is original_compilers
    )
    assert updated_settings.editor is original_editor
    assert updated_settings.cobol is original_cobol
    assert updated_settings.theme is theme
    assert storage.load() == updated_settings


def test_update_recent_projects_preserves_other_settings(
    tmp_path: Path,
) -> None:
    storage = SettingsStorage(
        tmp_path / "settings.json",
    )
    service = SettingsService(
        storage,
    )

    original_compilers = service.current.compilers
    original_editor = service.current.editor
    original_theme = service.current.theme

    recent_projects = RecentProjectsSettings(
        paths=(
            Path(
                "/a/project.json",
            ),
        ),
    )

    updated_settings = (
        service.update_recent_projects(
            recent_projects,
        )
    )

    assert (
        updated_settings.compilers
        is original_compilers
    )
    assert updated_settings.editor is original_editor
    assert updated_settings.theme is original_theme
    assert (
        updated_settings.recent_projects
        is recent_projects
    )
    assert storage.load() == updated_settings


def test_update_recent_projects_rejects_wrong_type(
    tmp_path: Path,
) -> None:
    service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )

    with pytest.raises(
        TypeError,
        match=(
            "Recent projects settings must be "
            "RecentProjectsSettings"
        ),
    ):
        service.update_recent_projects(
            object(),  # type: ignore[arg-type]
        )


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