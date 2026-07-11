"""Unit tests for the OpenCobol2 project application service."""

from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.project import (
    LaunchConfigurationNotFoundError,
    LinkedFileNotFoundError,
    Project,
    ProjectProperties,
    ProjectService,
    ProjectStorage,
    ProjectTaskNotFoundError,
    VirtualFolderNotFoundError,
    create_project,
)


def _service(tmp_path: Path) -> ProjectService:
    """Create a service around a freshly created project."""

    storage = ProjectStorage(tmp_path / "demo.ocproj.json")
    project = create_project(name="Demo", root_path=tmp_path)

    return ProjectService(storage, project=project)


def test_create_persists_project_immediately(tmp_path: Path) -> None:
    path = tmp_path / "demo.ocproj.json"
    project = create_project(name="Demo", root_path=tmp_path)

    ProjectService(ProjectStorage(path), project=project)

    assert path.exists()


def test_open_loads_existing_project(tmp_path: Path) -> None:
    service = _service(tmp_path)
    reopened = ProjectService(
        ProjectStorage(tmp_path / "demo.ocproj.json"),
    )

    assert reopened.current == service.current


def test_init_rejects_non_project_value(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "demo.ocproj.json")

    with pytest.raises(
        TypeError,
        match="must be Project",
    ):
        ProjectService(
            storage,
            project="not-a-project",  # type: ignore[arg-type]
        )


def test_apply_rejects_non_project_value(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(
        TypeError,
        match="must be Project",
    ):
        service.apply("not-a-project")  # type: ignore[arg-type]


def test_reload_reflects_external_changes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    storage = service.storage
    external = Project(
        project_id=service.current.project_id,
        name="Renamed",
        root_path=service.current.root_path,
    )
    storage.save(external)

    reloaded = service.reload()

    assert reloaded.name == "Renamed"
    assert service.current.name == "Renamed"


def test_update_properties(tmp_path: Path) -> None:
    service = _service(tmp_path)
    properties = ProjectProperties(output_directory="build")

    updated = service.update_properties(properties)

    assert updated.properties.output_directory == "build"


def test_update_excluded_patterns(tmp_path: Path) -> None:
    service = _service(tmp_path)

    updated = service.update_excluded_patterns(["*.tmp", "build/**"])

    assert updated.excluded_patterns == ("*.tmp", "build/**")


def test_update_environment_overrides(tmp_path: Path) -> None:
    service = _service(tmp_path)

    updated = service.update_environment_overrides(
        {"COB_COPY_DIR": "copy"},
    )

    assert updated.environment_overrides == {
        "COB_COPY_DIR": "copy",
    }


# --- virtual folders --------------------------------------------------------


def test_add_virtual_folder_at_root(tmp_path: Path) -> None:
    service = _service(tmp_path)

    updated = service.add_virtual_folder("Sources")

    assert len(updated.virtual_folders) == 1
    assert updated.virtual_folders[0].name == "Sources"


def test_add_virtual_folder_nested(tmp_path: Path) -> None:
    service = _service(tmp_path)
    parent = service.add_virtual_folder("Sources").virtual_folders[0]

    updated = service.add_virtual_folder(
        "Copybooks",
        parent_id=parent.folder_id,
    )

    parent_after = updated.virtual_folders[0]
    assert len(parent_after.virtual_folders) == 1
    assert parent_after.virtual_folders[0].name == "Copybooks"


def test_add_virtual_folder_rejects_unknown_parent(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)

    with pytest.raises(VirtualFolderNotFoundError):
        service.add_virtual_folder("Orphan", parent_id=uuid4())


def test_remove_virtual_folder_at_root(tmp_path: Path) -> None:
    service = _service(tmp_path)
    folder = service.add_virtual_folder("Sources").virtual_folders[0]

    updated = service.remove_virtual_folder(folder.folder_id)

    assert updated.virtual_folders == ()


def test_remove_nested_virtual_folder(tmp_path: Path) -> None:
    service = _service(tmp_path)
    parent = service.add_virtual_folder("Sources").virtual_folders[0]
    child = service.add_virtual_folder(
        "Copybooks",
        parent_id=parent.folder_id,
    ).virtual_folders[0].virtual_folders[0]

    updated = service.remove_virtual_folder(child.folder_id)

    assert updated.virtual_folders[0].virtual_folders == ()


def test_remove_virtual_folder_rejects_unknown_id(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)

    with pytest.raises(VirtualFolderNotFoundError):
        service.remove_virtual_folder(uuid4())


# --- linked files -------------------------------------------------------


def test_add_and_remove_linked_file(tmp_path: Path) -> None:
    service = _service(tmp_path)

    updated = service.add_linked_file(
        "shared.cpy",
        tmp_path.parent / "shared.cpy",
    )

    assert len(updated.linked_files) == 1
    linked_file_id = updated.linked_files[0].linked_file_id

    updated = service.remove_linked_file(linked_file_id)

    assert updated.linked_files == ()


def test_remove_linked_file_rejects_unknown_id(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(LinkedFileNotFoundError):
        service.remove_linked_file(uuid4())


def test_remove_linked_file_referenced_by_virtual_folder_fails(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    linked_file_id = service.add_linked_file(
        "shared.cpy",
        tmp_path.parent / "shared.cpy",
    ).linked_files[0].linked_file_id
    service.add_virtual_folder("Copybooks")
    folder_id = service.current.virtual_folders[0].folder_id

    from dataclasses import replace as _replace

    folders = service.current.virtual_folders
    updated_folder = _replace(
        folders[0],
        linked_file_ids=(linked_file_id,),
    )
    service.apply(
        _replace(
            service.current,
            virtual_folders=(updated_folder,),
        ),
    )

    with pytest.raises(ValueError, match="not part of the project"):
        service.remove_linked_file(linked_file_id)

    assert service.current.virtual_folders[0].folder_id == folder_id


# --- tasks --------------------------------------------------------------


def test_add_and_remove_task(tmp_path: Path) -> None:
    service = _service(tmp_path)

    updated = service.add_task(
        "Build",
        "cobc",
        arguments=["-x", "main.cob"],
    )

    assert len(updated.tasks) == 1
    task_id = updated.tasks[0].task_id

    updated = service.remove_task(task_id)

    assert updated.tasks == ()


def test_remove_task_rejects_unknown_id(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(ProjectTaskNotFoundError):
        service.remove_task(uuid4())


# --- launch configurations --------------------------------------------


def test_add_and_remove_launch_configuration(tmp_path: Path) -> None:
    service = _service(tmp_path)

    updated = service.add_launch_configuration(
        "Run",
        "bin/main",
    )

    assert len(updated.launch_configurations) == 1
    launch_id = updated.launch_configurations[0].launch_configuration_id

    updated = service.remove_launch_configuration(launch_id)

    assert updated.launch_configurations == ()


def test_remove_launch_configuration_rejects_unknown_id(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)

    with pytest.raises(LaunchConfigurationNotFoundError):
        service.remove_launch_configuration(uuid4())


def test_remove_default_launch_configuration_clears_default(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    launch_id = service.add_launch_configuration(
        "Run",
        "bin/main",
    ).launch_configurations[0].launch_configuration_id
    service.update_properties(
        ProjectProperties(
            default_launch_configuration_id=launch_id,
        ),
    )

    updated = service.remove_launch_configuration(launch_id)

    assert updated.properties.default_launch_configuration_id is None
    assert updated.launch_configurations == ()
