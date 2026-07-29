"""Unit tests for OpenCobol2 project file persistence."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.project import (
    LaunchConfiguration,
    LinkedFile,
    Project,
    ProjectFormatError,
    ProjectNotFoundError,
    ProjectProperties,
    ProjectStorage,
    ProjectTask,
    UnsupportedProjectVersionError,
    VirtualFolder,
    create_project,
)


def test_load_raises_when_file_missing(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "missing.ocproj.json")

    with pytest.raises(ProjectNotFoundError):
        storage.load()


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "demo.ocproj.json"
    storage = ProjectStorage(path)
    project = create_project(name="Demo", root_path=tmp_path)

    storage.save(project)

    assert path.exists()


def test_round_trip_preserves_full_project(tmp_path: Path) -> None:
    linked_file = LinkedFile(
        linked_file_id=uuid4(),
        display_name="shared.cpy",
        target_path=tmp_path.parent / "shared.cpy",
    )
    folder = VirtualFolder(
        folder_id=uuid4(),
        name="Copybooks",
        member_paths=("PAYROLL.cob",),
        linked_file_ids=(linked_file.linked_file_id,),
    )
    task = ProjectTask(
        task_id=uuid4(),
        name="Build",
        executable="cobc",
        arguments=("-x", "PAYROLL.cob"),
        working_directory="src",
        environment_overrides={"COB_CONFIG_DIR": "config"},
    )
    launch = LaunchConfiguration(
        launch_configuration_id=uuid4(),
        name="Run",
        executable_path="bin/PAYROLL",
        arguments=("--verbose",),
        environment_overrides={"COB_LIBRARY_PATH": "lib"},
    )
    project = Project(
        project_id=uuid4(),
        name="Payroll",
        root_path=tmp_path,
        properties=ProjectProperties(
            output_directory="out",
            default_compiler_profile_id=uuid4(),
            default_launch_configuration_id=(
                launch.launch_configuration_id
            ),
        ),
        excluded_patterns=("*.tmp", "out/**"),
        environment_overrides={"COB_COPY_DIR": "copy"},
        virtual_folders=(folder,),
        linked_files=(linked_file,),
        tasks=(task,),
        launch_configurations=(launch,),
    )

    storage = ProjectStorage(tmp_path / "demo.ocproj.json")
    storage.save(project)
    loaded = storage.load()

    assert loaded == project


def test_load_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "demo.ocproj.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(
        ProjectFormatError,
        match="invalid JSON",
    ):
        ProjectStorage(path).load()


def test_load_rejects_invalid_utf8(tmp_path: Path) -> None:
    """A truncated/wrong-encoding project file must raise the
    documented ProjectFormatError, not a raw UnicodeDecodeError --
    read_text(encoding="utf-8") can fail before json.loads() ever
    runs, and that failure sat outside the JSONDecodeError catch."""

    path = tmp_path / "demo.ocproj.json"
    path.write_bytes(
        b'{"schema_version": 1, "name": "caf\xe9"}',
    )

    with pytest.raises(
        ProjectFormatError,
        match="not valid UTF-8",
    ):
        ProjectStorage(path).load()


def test_load_rejects_pathologically_deep_virtual_folders(
    tmp_path: Path,
) -> None:
    """A very deeply nested virtual_folders structure must raise the
    documented ProjectFormatError, not a bare interpreter
    RecursionError -- RecursionError is a RuntimeError, which the
    decoder's except (TypeError, ValueError) clause didn't cover."""

    innermost = {
        "folder_id": str(uuid4()),
        "name": "leaf",
    }
    nested = innermost

    for _ in range(3000):
        nested = {
            "folder_id": str(uuid4()),
            "name": "wrapper",
            "virtual_folders": [nested],
        }

    path = tmp_path / "demo.ocproj.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": str(uuid4()),
                "name": "Deep",
                "root_path": str(tmp_path),
                "virtual_folders": [nested],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProjectFormatError):
        ProjectStorage(path).load()


def test_load_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "demo.ocproj.json"
    path.write_text(
        '{"schema_version": 99, "project_id": "'
        f"{uuid4()}"
        '", "name": "Demo", "root_path": "/x"}',
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedProjectVersionError):
        ProjectStorage(path).load()


def test_load_rejects_non_object_root(tmp_path: Path) -> None:
    path = tmp_path / "demo.ocproj.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(
        ProjectFormatError,
        match="must be an object",
    ):
        ProjectStorage(path).load()


def test_load_rejects_invalid_project_id(tmp_path: Path) -> None:
    path = tmp_path / "demo.ocproj.json"
    path.write_text(
        '{"schema_version": 1, "project_id": "not-a-uuid", '
        '"name": "Demo", "root_path": "/x"}',
        encoding="utf-8",
    )

    with pytest.raises(
        ProjectFormatError,
        match="must be a valid UUID",
    ):
        ProjectStorage(path).load()


def test_save_rejects_non_project_value(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path / "demo.ocproj.json")

    with pytest.raises(
        TypeError,
        match="must be Project",
    ):
        storage.save("not-a-project")  # type: ignore[arg-type]


def test_save_overwrites_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "demo.ocproj.json"
    storage = ProjectStorage(path)
    first = create_project(name="First", root_path=tmp_path)
    second = create_project(name="Second", root_path=tmp_path)

    storage.save(first)
    storage.save(second)
    loaded = storage.load()

    assert loaded.name == "Second"
