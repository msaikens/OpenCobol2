"""Unit tests for the OpenCobol2 project domain model."""

from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.project import (
    LaunchConfiguration,
    LinkedFile,
    Project,
    ProjectProperties,
    ProjectTask,
    VirtualFolder,
    create_project,
)


def _project(**overrides: object) -> Project:
    """Build a minimal valid project, applying field overrides."""

    defaults: dict[str, object] = {
        "project_id": uuid4(),
        "name": "Payroll",
        "root_path": Path("/source/payroll"),
    }
    defaults.update(overrides)

    return Project(**defaults)


# --- create_project -------------------------------------------------------


def test_create_project_generates_identity() -> None:
    project = create_project(
        name="Payroll",
        root_path="/source/payroll",
    )

    assert project.name == "Payroll"
    assert project.root_path == Path("/source/payroll")
    assert project.project_id is not None


# --- Project validation -----------------------------------------------------


def test_project_requires_non_empty_name() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        _project(name="   ")


def test_project_rejects_non_uuid_project_id() -> None:
    with pytest.raises(
        TypeError,
        match="must be a UUID",
    ):
        _project(project_id="not-a-uuid")


def test_project_rejects_invalid_schema_version() -> None:
    with pytest.raises(
        ValueError,
        match="must be positive",
    ):
        _project(schema_version=0)


def test_project_defaults_are_empty() -> None:
    project = _project()

    assert project.properties == ProjectProperties()
    assert project.excluded_patterns == ()
    assert project.virtual_folders == ()
    assert project.linked_files == ()
    assert project.tasks == ()
    assert project.launch_configurations == ()


def test_project_rejects_duplicate_virtual_folder_ids() -> None:
    folder_id = uuid4()
    folder_one = VirtualFolder(folder_id=folder_id, name="A")
    folder_two = VirtualFolder(folder_id=folder_id, name="B")

    with pytest.raises(
        ValueError,
        match="Virtual folder IDs must be unique",
    ):
        _project(virtual_folders=(folder_one, folder_two))


def test_project_rejects_duplicate_nested_virtual_folder_ids() -> None:
    folder_id = uuid4()
    child = VirtualFolder(folder_id=folder_id, name="Child")
    parent = VirtualFolder(
        folder_id=uuid4(),
        name="Parent",
        virtual_folders=(child,),
    )
    sibling_with_same_id = VirtualFolder(
        folder_id=folder_id,
        name="Sibling",
    )

    with pytest.raises(
        ValueError,
        match="Virtual folder IDs must be unique",
    ):
        _project(
            virtual_folders=(parent, sibling_with_same_id),
        )


def test_project_rejects_duplicate_linked_file_ids() -> None:
    linked_file_id = uuid4()
    linked_file_one = LinkedFile(
        linked_file_id=linked_file_id,
        display_name="a.cpy",
        target_path=Path("/external/a.cpy"),
    )
    linked_file_two = LinkedFile(
        linked_file_id=linked_file_id,
        display_name="b.cpy",
        target_path=Path("/external/b.cpy"),
    )

    with pytest.raises(
        ValueError,
        match="Linked file IDs must be unique",
    ):
        _project(
            linked_files=(linked_file_one, linked_file_two),
        )


def test_project_rejects_virtual_folder_referencing_unknown_linked_file() -> (
    None
):
    folder = VirtualFolder(
        folder_id=uuid4(),
        name="Copybooks",
        linked_file_ids=(uuid4(),),
    )

    with pytest.raises(
        ValueError,
        match="not part of the project",
    ):
        _project(virtual_folders=(folder,))


def test_project_accepts_virtual_folder_referencing_known_linked_file() -> (
    None
):
    linked_file = LinkedFile(
        linked_file_id=uuid4(),
        display_name="shared.cpy",
        target_path=Path("/external/shared.cpy"),
    )
    folder = VirtualFolder(
        folder_id=uuid4(),
        name="Copybooks",
        linked_file_ids=(linked_file.linked_file_id,),
    )

    project = _project(
        virtual_folders=(folder,),
        linked_files=(linked_file,),
    )

    assert project.get_linked_file(
        linked_file.linked_file_id,
    ) is linked_file


def test_project_rejects_duplicate_task_ids() -> None:
    task_id = uuid4()
    task_one = ProjectTask(
        task_id=task_id,
        name="Build",
        executable="cobc",
    )
    task_two = ProjectTask(
        task_id=task_id,
        name="Clean",
        executable="rm",
    )

    with pytest.raises(
        ValueError,
        match="Project task IDs must be unique",
    ):
        _project(tasks=(task_one, task_two))


def test_project_rejects_duplicate_launch_configuration_ids() -> None:
    launch_configuration_id = uuid4()
    launch_one = LaunchConfiguration(
        launch_configuration_id=launch_configuration_id,
        name="Run",
        executable_path="bin/main",
    )
    launch_two = LaunchConfiguration(
        launch_configuration_id=launch_configuration_id,
        name="Debug",
        executable_path="bin/main",
    )

    with pytest.raises(
        ValueError,
        match="Launch configuration IDs must be unique",
    ):
        _project(
            launch_configurations=(launch_one, launch_two),
        )


def test_project_rejects_unknown_default_launch_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="must reference an existing launch configuration",
    ):
        _project(
            properties=ProjectProperties(
                default_launch_configuration_id=uuid4(),
            ),
        )


def test_project_get_task_returns_none_when_missing() -> None:
    project = _project()

    assert project.get_task(uuid4()) is None


# --- VirtualFolder / LinkedFile / ProjectTask / LaunchConfiguration --------


def test_virtual_folder_requires_non_empty_name() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        VirtualFolder(folder_id=uuid4(), name="  ")


def test_virtual_folder_rejects_absolute_member_path() -> None:
    with pytest.raises(
        ValueError,
        match="must be relative",
    ):
        VirtualFolder(
            folder_id=uuid4(),
            name="Sources",
            member_paths=("/etc/passwd",),
        )


def test_virtual_folder_rejects_traversing_member_path() -> None:
    with pytest.raises(
        ValueError,
        match="must not traverse",
    ):
        VirtualFolder(
            folder_id=uuid4(),
            name="Sources",
            member_paths=("../outside.cob",),
        )


def test_linked_file_requires_non_empty_display_name() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        LinkedFile(
            linked_file_id=uuid4(),
            display_name="  ",
            target_path=Path("/external/shared.cpy"),
        )


def test_project_task_requires_non_empty_executable() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        ProjectTask(
            task_id=uuid4(),
            name="Build",
            executable="  ",
        )


def test_project_task_rejects_absolute_working_directory() -> None:
    with pytest.raises(
        ValueError,
        match="must be relative",
    ):
        ProjectTask(
            task_id=uuid4(),
            name="Build",
            executable="cobc",
            working_directory="/tmp",
        )


def test_launch_configuration_rejects_absolute_executable_path() -> None:
    with pytest.raises(
        ValueError,
        match="must be relative",
    ):
        LaunchConfiguration(
            launch_configuration_id=uuid4(),
            name="Run",
            executable_path="/bin/main",
        )


def test_project_properties_rejects_absolute_output_directory() -> None:
    with pytest.raises(
        ValueError,
        match="must be relative",
    ):
        ProjectProperties(output_directory="/bin")
