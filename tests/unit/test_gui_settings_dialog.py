"""Unit tests for the Settings/Preferences dialog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from opencobol2.compiler import CobolSourceFormat
from opencobol2.gui.settings_dialog import (
    create_show_settings_handler,
    SettingsDialog,
)
from opencobol2.settings import (
    ExternalToolSettings,
    SettingsService,
    SettingsStorage,
)
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    LIGHT_THEME_ID,
)


def _build_service(
    tmp_path: Path,
) -> SettingsService:
    return SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )


def test_dialog_loads_current_settings(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = SettingsDialog(
        settings_service=service,
        theme_registry=create_builtin_theme_registry(),
    )

    assert dialog._font_size_spin.value() == 11
    assert dialog._tab_width_spin.value() == 4
    assert dialog._insert_spaces_check.isChecked()
    # QComboBox.currentData() marshals a StrEnum through QVariant as a plain
    # str, not the enum member itself; CobolSourceFormat is a StrEnum, so
    # equality (not identity) is the correct comparison here.
    assert (
        dialog._source_format_combo.currentData()
        == CobolSourceFormat.FIXED
    )
    assert (
        dialog._guide_checks[
            "show_sequence_area"
        ].isChecked()
    )
    assert (
        dialog._theme_combo.currentData()
        == DARK_THEME_ID
    )
    assert (
        dialog._git_executable_path_edit.text()
        == ""
    )
    assert dialog._show_minimap_check.isChecked()
    assert not dialog._autosave_check.isChecked()
    assert (
        dialog._autosave_interval_spin.value()
        == 60
    )


def test_dialog_lists_every_registered_theme(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    registry = create_builtin_theme_registry()
    dialog = SettingsDialog(
        settings_service=service,
        theme_registry=registry,
    )

    assert dialog._theme_combo.count() == len(
        registry.themes,
    )


def test_apply_and_accept_persists_all_sections(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = SettingsDialog(
        settings_service=service,
        theme_registry=create_builtin_theme_registry(),
    )

    dialog._font_family_edit.setText(
        "Cascadia Mono",
    )
    dialog._font_size_spin.setValue(
        18,
    )
    dialog._tab_width_spin.setValue(
        2,
    )
    dialog._insert_spaces_check.setChecked(
        False,
    )
    dialog._auto_indent_check.setChecked(
        False,
    )
    dialog._indentation_width_spin.setValue(
        8,
    )
    dialog._code_folding_check.setChecked(
        False,
    )
    dialog._show_minimap_check.setChecked(
        False,
    )
    dialog._autosave_check.setChecked(
        True,
    )
    dialog._autosave_interval_spin.setValue(
        30,
    )
    format_index = (
        dialog._source_format_combo.findData(
            CobolSourceFormat.FREE,
        )
    )
    dialog._source_format_combo.setCurrentIndex(
        format_index,
    )
    dialog._guide_checks[
        "show_sequence_area"
    ].setChecked(
        False,
    )
    theme_index = dialog._theme_combo.findData(
        LIGHT_THEME_ID,
    )
    dialog._theme_combo.setCurrentIndex(
        theme_index,
    )

    dialog._apply_and_accept()

    assert (
        dialog.result()
        == dialog.DialogCode.Accepted
    )

    reloaded = SettingsService(
        service.storage,
    )
    assert (
        reloaded.current.editor.font_family
        == "Cascadia Mono"
    )
    assert reloaded.current.editor.font_size == 18
    assert reloaded.current.editor.tab_width == 2
    assert (
        reloaded.current.editor.insert_spaces
        is False
    )
    assert (
        reloaded.current.editor.automatic_indentation
        is False
    )
    assert (
        reloaded.current.editor.indentation_width
        == 8
    )
    assert (
        reloaded.current.editor.code_folding
        is False
    )
    assert (
        reloaded.current.editor.show_minimap
        is False
    )
    assert (
        reloaded.current.editor.autosave_enabled
        is True
    )
    assert (
        reloaded.current.editor.autosave_interval_seconds
        == 30
    )
    assert (
        reloaded.current.cobol.default_source_format
        is CobolSourceFormat.FREE
    )
    assert (
        reloaded.current.cobol.guides.show_sequence_area
        is False
    )
    assert (
        reloaded.current.theme.active_theme_id
        == "light"
    )


def test_apply_and_accept_persists_git_executable_path(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = SettingsDialog(
        settings_service=service,
        theme_registry=create_builtin_theme_registry(),
    )
    git_path = tmp_path / "custom-git.exe"

    dialog._git_executable_path_edit.setText(
        str(git_path),
    )
    dialog._apply_and_accept()

    reloaded = SettingsService(
        service.storage,
    )
    assert (
        reloaded.current.external_tools.git_executable_path
        == git_path
    )


def test_apply_and_accept_clears_git_executable_path_when_blank(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    service.update_external_tools(
        ExternalToolSettings(
            git_executable_path=(
                tmp_path / "custom-git.exe"
            ),
        )
    )
    dialog = SettingsDialog(
        settings_service=service,
        theme_registry=create_builtin_theme_registry(),
    )
    assert (
        dialog._git_executable_path_edit.text()
        == str(
            tmp_path / "custom-git.exe",
        )
    )

    dialog._git_executable_path_edit.setText(
        "",
    )
    dialog._apply_and_accept()

    reloaded = SettingsService(
        service.storage,
    )
    assert (
        reloaded.current.external_tools.git_executable_path
        is None
    )


def test_cancel_does_not_persist_changes(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    dialog = SettingsDialog(
        settings_service=service,
        theme_registry=create_builtin_theme_registry(),
    )

    dialog._font_size_spin.setValue(
        99,
    )
    dialog.reject()

    reloaded = SettingsService(
        service.storage,
    )
    assert reloaded.current.editor.font_size == 11


def test_dialog_rejects_non_settings_service(
    qapp,
) -> None:
    with pytest.raises(
        TypeError,
        match="Settings dialog service must be SettingsService",
    ):
        SettingsDialog(
            settings_service=object(),  # type: ignore[arg-type]
            theme_registry=create_builtin_theme_registry(),
        )


def test_dialog_rejects_non_theme_registry(
    qapp,
    tmp_path: Path,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Settings dialog theme registry must be "
            "ThemeRegistry"
        ),
    ):
        SettingsDialog(
            settings_service=_build_service(
                tmp_path,
            ),
            theme_registry=object(),  # type: ignore[arg-type]
        )


def test_show_settings_handler_calls_on_applied_when_accepted(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    applied = []
    handler = create_show_settings_handler(
        settings_service=service,
        theme_registry=create_builtin_theme_registry(),
        on_applied=applied.append,
    )

    with patch(
        "opencobol2.gui.settings_dialog."
        "SettingsDialog.exec",
        return_value=1,
    ):
        handler(
            None,
        )

    assert len(applied) == 1
    assert applied[0] is service.current


def test_show_settings_handler_skips_on_applied_when_cancelled(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    applied = []
    handler = create_show_settings_handler(
        settings_service=service,
        theme_registry=create_builtin_theme_registry(),
        on_applied=applied.append,
    )

    with patch(
        "opencobol2.gui.settings_dialog."
        "SettingsDialog.exec",
        return_value=0,
    ):
        handler(
            None,
        )

    assert applied == []
