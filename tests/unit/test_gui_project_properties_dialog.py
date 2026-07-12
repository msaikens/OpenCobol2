"""Unit tests for the Project Properties dialog."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from opencobol2.compiler.providers import (
    CompilerProfile,
    CUSTOM_COMPILER_PROVIDER_ID,
)
from opencobol2.gui.project_properties_dialog import (
    ProjectPropertiesDialog,
)
from opencobol2.project import create_project
from opencobol2.settings import (
    CompilerSettings,
    SettingsService,
    SettingsStorage,
)


def _build_service(
    tmp_path: Path,
) -> SettingsService:
    return SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )


def test_dialog_defaults_to_global_default_when_project_has_no_profile(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    dialog = ProjectPropertiesDialog(
        project=project,
        settings_service=service,
    )

    assert (
        dialog._compiler_profile_combo.currentIndex()
        == 0
    )
    assert (
        dialog._compiler_profile_combo.currentText()
        == "(Use global default)"
    )
    assert (
        dialog._compiler_profile_combo.currentData()
        is None
    )


def test_dialog_preselects_the_projects_configured_profile(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    custom_profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="My Custom Compiler",
    )
    existing = service.current.compilers
    service.update_compilers(
        CompilerSettings(
            default_profile_id=(
                existing.default_profile_id
            ),
            profiles=(
                *existing.profiles,
                custom_profile,
            ),
        )
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project = replace(
        project,
        properties=replace(
            project.properties,
            default_compiler_profile_id=(
                custom_profile.profile_id
            ),
        ),
    )

    dialog = ProjectPropertiesDialog(
        project=project,
        settings_service=service,
    )

    assert (
        dialog._compiler_profile_combo.currentText()
        == "My Custom Compiler"
    )


def test_dialog_falls_back_to_global_default_for_a_deleted_profile(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    # References a profile ID that isn't (or is no longer) configured.
    project = replace(
        project,
        properties=replace(
            project.properties,
            default_compiler_profile_id=(
                CompilerProfile(
                    provider_id=CUSTOM_COMPILER_PROVIDER_ID,
                    display_name="Ghost",
                ).profile_id
            ),
        ),
    )

    dialog = ProjectPropertiesDialog(
        project=project,
        settings_service=service,
    )

    assert (
        dialog._compiler_profile_combo.currentIndex()
        == 0
    )


def test_accepting_selects_a_specific_profile(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    custom_profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="My Custom Compiler",
    )
    existing = service.current.compilers
    service.update_compilers(
        CompilerSettings(
            default_profile_id=(
                existing.default_profile_id
            ),
            profiles=(
                *existing.profiles,
                custom_profile,
            ),
        )
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    dialog = ProjectPropertiesDialog(
        project=project,
        settings_service=service,
    )
    index = (
        dialog._compiler_profile_combo.findData(
            custom_profile.profile_id,
        )
    )
    dialog._compiler_profile_combo.setCurrentIndex(
        index,
    )

    dialog._apply_and_accept()

    assert (
        dialog.result()
        == dialog.DialogCode.Accepted
    )
    assert (
        dialog.updated_project.properties
        .default_compiler_profile_id
        == custom_profile.profile_id
    )
    # The original project object must not be mutated in place.
    assert (
        project.properties.default_compiler_profile_id
        is None
    )


def test_accepting_can_revert_to_global_default(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project = replace(
        project,
        properties=replace(
            project.properties,
            default_compiler_profile_id=(
                service.current.compilers
                .default_profile_id
            ),
        ),
    )

    dialog = ProjectPropertiesDialog(
        project=project,
        settings_service=service,
    )
    dialog._compiler_profile_combo.setCurrentIndex(
        0,
    )

    dialog._apply_and_accept()

    assert (
        dialog.updated_project.properties
        .default_compiler_profile_id
        is None
    )


def test_cancel_does_not_set_updated_project(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    dialog = ProjectPropertiesDialog(
        project=project,
        settings_service=service,
    )
    dialog.reject()

    assert dialog.updated_project is None


def test_dialog_rejects_non_project(
    qapp,
    tmp_path: Path,
) -> None:
    service = _build_service(
        tmp_path,
    )

    with pytest.raises(
        TypeError,
        match=(
            "Project properties dialog project must be Project"
        ),
    ):
        ProjectPropertiesDialog(
            project=object(),  # type: ignore[arg-type]
            settings_service=service,
        )


def test_dialog_rejects_non_settings_service(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    with pytest.raises(
        TypeError,
        match=(
            "Project properties dialog service must be "
            "SettingsService"
        ),
    ):
        ProjectPropertiesDialog(
            project=project,
            settings_service=object(),  # type: ignore[arg-type]
        )
