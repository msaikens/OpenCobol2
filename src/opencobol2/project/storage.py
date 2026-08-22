"""JSON persistence for OpenCobol2 project files."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from uuid import UUID

from opencobol2.project.models import (
    CURRENT_PROJECT_SCHEMA_VERSION,
    LaunchConfiguration,
    LinkedFile,
    Project,
    ProjectProperties,
    ProjectTask,
    VirtualFolder,
)


class ProjectFormatError(ValueError):
    """Raised when a persisted project file cannot be decoded."""


class UnsupportedProjectVersionError(
    ProjectFormatError,
):
    """Raised when a persisted project file uses an unsupported schema."""


class ProjectNotFoundError(FileNotFoundError):
    """Raised when a project file does not exist at the expected path."""


class ProjectStorage:
    """Loads and saves one persisted OpenCobol2 project file."""

    __slots__ = (
        "_path",
    )

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        """Initialize project storage bound to an explicit file path."""

        self._path = Path(
            path,
        )

    @property
    def path(
        self,
    ) -> Path:
        """Return the project file path."""

        return self._path

    def load(
        self,
    ) -> Project:
        """Load the persisted project file."""

        if not self._path.exists():
            raise ProjectNotFoundError(
                f"Project file does not exist: {self._path}"
            )

        try:
            raw_project = json.loads(
                self._path.read_text(
                    encoding="utf-8",
                )
            )
        except UnicodeDecodeError as error:
            raise ProjectFormatError(
                "Project file is not valid UTF-8."
            ) from error
        except json.JSONDecodeError as error:
            raise ProjectFormatError(
                "Project file contains invalid JSON."
            ) from error

        return _decode_project(
            raw_project,
        )

    def save(
        self,
        project: Project,
    ) -> Path:
        """Persist a project through a same-directory replacement file."""

        if not isinstance(
            project,
            Project,
        ):
            raise TypeError(
                "Project must be Project."
            )

        serialized_project = json.dumps(
            _encode_project(
                project,
            ),
            ensure_ascii=False,
            indent=2,
        )

        payload = (
            serialized_project + "\n"
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


def describe_project_file(
    path: Path,
) -> str:
    """Return a project file's display name for a recent-projects list.

    Reads just enough of the file to recover its stored project name.
    Falls back to the file's own stem (its filename without extension)
    if the file can't be read or parsed, since a recent-projects entry
    should still show something reasonable rather than disappearing or
    raising just because its target became briefly unreadable (a
    network drive blip, a file mid-write) at exactly the moment the
    list is rendered.

    :param path: The project file to describe.
    :returns: The project's stored name, or `path.stem` if it can't be
        loaded.
    """

    try:
        return ProjectStorage(
            path,
        ).load().name
    except (
        OSError,
        ValueError,
    ):
        return path.stem


def _encode_project(
    project: Project,
) -> dict[str, Any]:
    """Encode a typed project into JSON-compatible values."""

    return {
        "schema_version": project.schema_version,
        "project_id": str(
            project.project_id,
        ),
        "name": project.name,
        "root_path": str(
            project.root_path,
        ),
        "properties": _encode_properties(
            project.properties,
        ),
        "excluded_patterns": list(
            project.excluded_patterns,
        ),
        "environment_overrides": dict(
            sorted(
                project.environment_overrides.items(),
            )
        ),
        "virtual_folders": [
            _encode_virtual_folder(
                folder,
            )
            for folder in project.virtual_folders
        ],
        "linked_files": [
            _encode_linked_file(
                linked_file,
            )
            for linked_file in project.linked_files
        ],
        "tasks": [
            _encode_task(
                task,
            )
            for task in project.tasks
        ],
        "launch_configurations": [
            _encode_launch_configuration(
                launch_configuration,
            )
            for launch_configuration in (
                project.launch_configurations
            )
        ],
    }


def _encode_properties(
    properties: ProjectProperties,
) -> dict[str, Any]:
    """Encode project build and launch defaults."""

    return {
        "output_directory": properties.output_directory,
        "default_compiler_profile_id": (
            str(
                properties.default_compiler_profile_id,
            )
            if properties.default_compiler_profile_id is not None
            else None
        ),
        "default_launch_configuration_id": (
            str(
                properties.default_launch_configuration_id,
            )
            if (
                properties.default_launch_configuration_id
                is not None
            )
            else None
        ),
    }


def _encode_virtual_folder(
    folder: VirtualFolder,
) -> dict[str, Any]:
    """Encode one virtual folder and its nested children."""

    return {
        "folder_id": str(
            folder.folder_id,
        ),
        "name": folder.name,
        "virtual_folders": [
            _encode_virtual_folder(
                child,
            )
            for child in folder.virtual_folders
        ],
        "member_paths": list(
            folder.member_paths,
        ),
        "linked_file_ids": [
            str(
                linked_file_id,
            )
            for linked_file_id in folder.linked_file_ids
        ],
    }


def _encode_linked_file(
    linked_file: LinkedFile,
) -> dict[str, Any]:
    """Encode one linked file."""

    return {
        "linked_file_id": str(
            linked_file.linked_file_id,
        ),
        "display_name": linked_file.display_name,
        "target_path": str(
            linked_file.target_path,
        ),
    }


def _encode_task(
    task: ProjectTask,
) -> dict[str, Any]:
    """Encode one project task."""

    return {
        "task_id": str(
            task.task_id,
        ),
        "name": task.name,
        "executable": task.executable,
        "arguments": list(
            task.arguments,
        ),
        "working_directory": task.working_directory,
        "environment_overrides": dict(
            sorted(
                task.environment_overrides.items(),
            )
        ),
    }


def _encode_launch_configuration(
    launch_configuration: LaunchConfiguration,
) -> dict[str, Any]:
    """Encode one launch configuration."""

    return {
        "launch_configuration_id": str(
            launch_configuration.launch_configuration_id,
        ),
        "name": launch_configuration.name,
        "executable_path": (
            launch_configuration.executable_path
        ),
        "arguments": list(
            launch_configuration.arguments,
        ),
        "working_directory": (
            launch_configuration.working_directory
        ),
        "environment_overrides": dict(
            sorted(
                launch_configuration
                .environment_overrides
                .items(),
            )
        ),
    }


def _decode_project(
    raw_project: Any,
) -> Project:
    """Decode persisted JSON values into a typed project."""

    root = _require_mapping(
        raw_project,
        "Project root",
    )

    schema_version = _require_integer(
        root.get(
            "schema_version",
        ),
        "Project schema version",
    )

    if (
        schema_version
        != CURRENT_PROJECT_SCHEMA_VERSION
    ):
        raise UnsupportedProjectVersionError(
            "Unsupported project schema version: "
            f"{schema_version}. "
            "Current version is "
            f"{CURRENT_PROJECT_SCHEMA_VERSION}."
        )

    try:
        return Project(
            schema_version=schema_version,
            project_id=_require_uuid(
                root.get(
                    "project_id",
                ),
                "Project ID",
            ),
            name=_require_string(
                root.get(
                    "name",
                ),
                "Project name",
            ),
            root_path=Path(
                _require_string(
                    root.get(
                        "root_path",
                    ),
                    "Project root path",
                ),
            ),
            properties=_decode_properties(
                root.get(
                    "properties",
                    {},
                ),
            ),
            excluded_patterns=tuple(
                _require_list(
                    root.get(
                        "excluded_patterns",
                        [],
                    ),
                    "Project excluded patterns",
                ),
            ),
            environment_overrides=_require_string_mapping(
                root.get(
                    "environment_overrides",
                    {},
                ),
                "Project environment overrides",
            ),
            virtual_folders=tuple(
                _decode_virtual_folder(
                    raw_folder,
                )
                for raw_folder in _require_list(
                    root.get(
                        "virtual_folders",
                        [],
                    ),
                    "Project virtual folders",
                )
            ),
            linked_files=tuple(
                _decode_linked_file(
                    raw_linked_file,
                )
                for raw_linked_file in _require_list(
                    root.get(
                        "linked_files",
                        [],
                    ),
                    "Project linked files",
                )
            ),
            tasks=tuple(
                _decode_task(
                    raw_task,
                )
                for raw_task in _require_list(
                    root.get(
                        "tasks",
                        [],
                    ),
                    "Project tasks",
                )
            ),
            launch_configurations=tuple(
                _decode_launch_configuration(
                    raw_launch_configuration,
                )
                for raw_launch_configuration in _require_list(
                    root.get(
                        "launch_configurations",
                        [],
                    ),
                    "Project launch configurations",
                )
            ),
        )
    except ProjectFormatError:
        raise
    except (
        TypeError,
        ValueError,
        RecursionError,
    ) as error:
        # RecursionError is a RuntimeError, not a ValueError/TypeError
        # -- an unusually deep (but not otherwise invalid) nested
        # virtual_folders structure would otherwise crash with a bare
        # interpreter recursion error instead of this same clean,
        # documented format error every other decode failure gets.
        raise ProjectFormatError(
            f"Project file contains an invalid value: {error}"
        ) from error


def _decode_properties(
    raw_properties: Any,
) -> ProjectProperties:
    """Decode project build and launch defaults."""

    properties = _require_mapping(
        raw_properties,
        "Project properties",
    )
    defaults = ProjectProperties()

    return ProjectProperties(
        output_directory=_require_string(
            properties.get(
                "output_directory",
                defaults.output_directory,
            ),
            "Project output directory",
        ),
        default_compiler_profile_id=_optional_uuid(
            properties.get(
                "default_compiler_profile_id",
            ),
            "Default compiler profile ID",
        ),
        default_launch_configuration_id=_optional_uuid(
            properties.get(
                "default_launch_configuration_id",
            ),
            "Default launch configuration ID",
        ),
    )


def _decode_virtual_folder(
    raw_folder: Any,
) -> VirtualFolder:
    """Decode one virtual folder and its nested children."""

    folder = _require_mapping(
        raw_folder,
        "Virtual folder",
    )

    return VirtualFolder(
        folder_id=_require_uuid(
            folder.get(
                "folder_id",
            ),
            "Virtual folder ID",
        ),
        name=_require_string(
            folder.get(
                "name",
            ),
            "Virtual folder name",
        ),
        virtual_folders=tuple(
            _decode_virtual_folder(
                raw_child,
            )
            for raw_child in _require_list(
                folder.get(
                    "virtual_folders",
                    [],
                ),
                "Virtual folder children",
            )
        ),
        member_paths=tuple(
            _require_list(
                folder.get(
                    "member_paths",
                    [],
                ),
                "Virtual folder member paths",
            ),
        ),
        linked_file_ids=tuple(
            _require_uuid(
                raw_linked_file_id,
                "Virtual folder linked file ID",
            )
            for raw_linked_file_id in _require_list(
                folder.get(
                    "linked_file_ids",
                    [],
                ),
                "Virtual folder linked file IDs",
            )
        ),
    )


def _decode_linked_file(
    raw_linked_file: Any,
) -> LinkedFile:
    """Decode one linked file."""

    linked_file = _require_mapping(
        raw_linked_file,
        "Linked file",
    )

    return LinkedFile(
        linked_file_id=_require_uuid(
            linked_file.get(
                "linked_file_id",
            ),
            "Linked file ID",
        ),
        display_name=_require_string(
            linked_file.get(
                "display_name",
            ),
            "Linked file display name",
        ),
        target_path=Path(
            _require_string(
                linked_file.get(
                    "target_path",
                ),
                "Linked file target path",
            ),
        ),
    )


def _decode_task(
    raw_task: Any,
) -> ProjectTask:
    """Decode one project task."""

    task = _require_mapping(
        raw_task,
        "Project task",
    )

    return ProjectTask(
        task_id=_require_uuid(
            task.get(
                "task_id",
            ),
            "Project task ID",
        ),
        name=_require_string(
            task.get(
                "name",
            ),
            "Project task name",
        ),
        executable=_require_string(
            task.get(
                "executable",
            ),
            "Project task executable",
        ),
        arguments=tuple(
            _require_list(
                task.get(
                    "arguments",
                    [],
                ),
                "Project task arguments",
            ),
        ),
        working_directory=_optional_string(
            task.get(
                "working_directory",
            ),
            "Project task working directory",
        ),
        environment_overrides=_require_string_mapping(
            task.get(
                "environment_overrides",
                {},
            ),
            "Project task environment overrides",
        ),
    )


def _decode_launch_configuration(
    raw_launch_configuration: Any,
) -> LaunchConfiguration:
    """Decode one launch configuration."""

    launch_configuration = _require_mapping(
        raw_launch_configuration,
        "Launch configuration",
    )

    return LaunchConfiguration(
        launch_configuration_id=_require_uuid(
            launch_configuration.get(
                "launch_configuration_id",
            ),
            "Launch configuration ID",
        ),
        name=_require_string(
            launch_configuration.get(
                "name",
            ),
            "Launch configuration name",
        ),
        executable_path=_require_string(
            launch_configuration.get(
                "executable_path",
            ),
            "Launch configuration executable path",
        ),
        arguments=tuple(
            _require_list(
                launch_configuration.get(
                    "arguments",
                    [],
                ),
                "Launch configuration arguments",
            ),
        ),
        working_directory=_optional_string(
            launch_configuration.get(
                "working_directory",
            ),
            "Launch configuration working directory",
        ),
        environment_overrides=_require_string_mapping(
            launch_configuration.get(
                "environment_overrides",
                {},
            ),
            "Launch configuration environment overrides",
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
        raise ProjectFormatError(
            f"{name} must be an object."
        )

    return value


def _require_list(
    value: Any,
    name: str,
) -> list[Any]:
    """Require a JSON array value."""

    if not isinstance(
        value,
        list,
    ):
        raise ProjectFormatError(
            f"{name} must be an array."
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
            raise ProjectFormatError(
                f"{name} keys must be strings."
            )

        if not isinstance(
            item_value,
            str,
        ):
            raise ProjectFormatError(
                f"{name} values must be strings."
            )

        result[key] = item_value

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
        raise ProjectFormatError(
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


def _require_uuid(
    value: Any,
    name: str,
) -> UUID:
    """Require a valid UUID string."""

    raw_value = _require_string(
        value,
        name,
    )

    try:
        return UUID(
            raw_value,
        )
    except ValueError as error:
        raise ProjectFormatError(
            f"{name} must be a valid UUID."
        ) from error


def _optional_uuid(
    value: Any,
    name: str,
) -> UUID | None:
    """Require a valid UUID string or null."""

    if value is None:
        return None

    return _require_uuid(
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
        raise ProjectFormatError(
            f"{name} must be an integer."
        )

    return value
