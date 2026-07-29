"""Typed models for a persisted OpenCobol2 project."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4


CURRENT_PROJECT_SCHEMA_VERSION = 1


class TaskExecutionStatus(StrEnum):
    """Outcome of invoking one project task or launch configuration."""

    COMPLETED = "completed"
    TIMED_OUT = "timed-out"
    FAILED_TO_START = "failed-to-start"


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskRunResult:
    """Captured result from running one task or launch configuration."""

    run_id: UUID
    command: tuple[str, ...]
    status: TaskExecutionStatus
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Normalize and validate captured task run state."""

        if not isinstance(
            self.run_id,
            UUID,
        ):
            raise TypeError(
                "Task run ID must be a UUID."
            )

        command = tuple(
            str(argument)
            for argument in self.command
        )

        if not command:
            raise ValueError(
                "Task run command must not be empty."
            )

        if not isinstance(
            self.status,
            TaskExecutionStatus,
        ):
            raise TypeError(
                "Task run status must be TaskExecutionStatus."
            )

        if (
            self.return_code is not None
            and (
                not isinstance(
                    self.return_code,
                    int,
                )
                or isinstance(
                    self.return_code,
                    bool,
                )
            )
        ):
            raise TypeError(
                "Task run return code must be an integer or None."
            )

        if not isinstance(
            self.stdout,
            str,
        ):
            raise TypeError(
                "Task run stdout must be a string."
            )

        if not isinstance(
            self.stderr,
            str,
        ):
            raise TypeError(
                "Task run stderr must be a string."
            )

        if (
            not isinstance(
                self.elapsed_seconds,
                (
                    int,
                    float,
                ),
            )
            or isinstance(
                self.elapsed_seconds,
                bool,
            )
        ):
            raise TypeError(
                "Task run elapsed seconds must be numeric."
            )

        if self.elapsed_seconds < 0:
            raise ValueError(
                "Task run elapsed seconds must not be negative."
            )

        if (
            self.error_message is not None
            and not isinstance(
                self.error_message,
                str,
            )
        ):
            raise TypeError(
                "Task run error message must be a string or None."
            )

        object.__setattr__(
            self,
            "command",
            command,
        )
        object.__setattr__(
            self,
            "elapsed_seconds",
            float(
                self.elapsed_seconds,
            ),
        )

    @property
    def completed(
        self,
    ) -> bool:
        """Return whether the task process completed."""

        return (
            self.status
            is TaskExecutionStatus.COMPLETED
        )

    @property
    def succeeded(
        self,
    ) -> bool:
        """Return whether the task completed with return code zero."""

        return (
            self.completed
            and self.return_code == 0
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class LinkedFile:
    """One file included in a project from outside its root."""

    linked_file_id: UUID
    display_name: str
    target_path: Path

    def __post_init__(self) -> None:
        """Normalize and validate linked file state."""

        if not isinstance(
            self.linked_file_id,
            UUID,
        ):
            raise TypeError(
                "Linked file ID must be a UUID."
            )

        display_name = _require_non_empty_string(
            self.display_name,
            "Linked file display name",
        )
        target_path = Path(
            self.target_path,
        )

        if not str(
            target_path,
        ):
            raise ValueError(
                "Linked file target path must not be empty."
            )

        object.__setattr__(
            self,
            "display_name",
            display_name,
        )
        object.__setattr__(
            self,
            "target_path",
            target_path,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class VirtualFolder:
    """One organizational folder in a project tree.

    Virtual folders group project members for display purposes only;
    they do not correspond to physical directories on disk.
    """

    folder_id: UUID
    name: str
    virtual_folders: tuple["VirtualFolder", ...] = ()
    member_paths: tuple[str, ...] = ()
    linked_file_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        """Normalize and validate virtual folder state."""

        if not isinstance(
            self.folder_id,
            UUID,
        ):
            raise TypeError(
                "Virtual folder ID must be a UUID."
            )

        name = _require_non_empty_string(
            self.name,
            "Virtual folder name",
        )

        virtual_folders = tuple(
            self.virtual_folders,
        )

        if not all(
            isinstance(
                folder,
                VirtualFolder,
            )
            for folder in virtual_folders
        ):
            raise TypeError(
                "Virtual folder children must contain "
                "VirtualFolder instances."
            )

        member_paths = tuple(
            _require_relative_project_path(
                member_path,
                "Virtual folder member path",
            )
            for member_path in self.member_paths
        )

        linked_file_ids = tuple(
            self.linked_file_ids,
        )

        if not all(
            isinstance(
                linked_file_id,
                UUID,
            )
            for linked_file_id in linked_file_ids
        ):
            raise TypeError(
                "Virtual folder linked file references must "
                "contain UUID instances."
            )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "virtual_folders",
            virtual_folders,
        )
        object.__setattr__(
            self,
            "member_paths",
            member_paths,
        )
        object.__setattr__(
            self,
            "linked_file_ids",
            linked_file_ids,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectTask:
    """One user-defined command a project can run."""

    task_id: UUID
    name: str
    executable: str
    arguments: tuple[str, ...] = ()
    working_directory: str | None = None
    environment_overrides: Mapping[str, str] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        """Normalize and validate project task state."""

        if not isinstance(
            self.task_id,
            UUID,
        ):
            raise TypeError(
                "Project task ID must be a UUID."
            )

        name = _require_non_empty_string(
            self.name,
            "Project task name",
        )
        executable = _require_non_empty_string(
            self.executable,
            "Project task executable",
        )
        arguments = _require_string_tuple(
            self.arguments,
            "Project task arguments",
        )
        working_directory = (
            None
            if self.working_directory is None
            else _require_relative_project_path(
                self.working_directory,
                "Project task working directory",
            )
        )
        environment_overrides = _require_string_mapping(
            self.environment_overrides,
            "Project task environment overrides",
        )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "executable",
            executable,
        )
        object.__setattr__(
            self,
            "arguments",
            arguments,
        )
        object.__setattr__(
            self,
            "working_directory",
            working_directory,
        )
        object.__setattr__(
            self,
            "environment_overrides",
            environment_overrides,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class LaunchConfiguration:
    """One configuration for running or debugging a built program."""

    launch_configuration_id: UUID
    name: str
    executable_path: str
    arguments: tuple[str, ...] = ()
    working_directory: str | None = None
    environment_overrides: Mapping[str, str] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        """Normalize and validate launch configuration state."""

        if not isinstance(
            self.launch_configuration_id,
            UUID,
        ):
            raise TypeError(
                "Launch configuration ID must be a UUID."
            )

        name = _require_non_empty_string(
            self.name,
            "Launch configuration name",
        )
        executable_path = _require_relative_project_path(
            self.executable_path,
            "Launch configuration executable path",
        )
        arguments = _require_string_tuple(
            self.arguments,
            "Launch configuration arguments",
        )
        working_directory = (
            None
            if self.working_directory is None
            else _require_relative_project_path(
                self.working_directory,
                "Launch configuration working directory",
            )
        )
        environment_overrides = _require_string_mapping(
            self.environment_overrides,
            "Launch configuration environment overrides",
        )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "executable_path",
            executable_path,
        )
        object.__setattr__(
            self,
            "arguments",
            arguments,
        )
        object.__setattr__(
            self,
            "working_directory",
            working_directory,
        )
        object.__setattr__(
            self,
            "environment_overrides",
            environment_overrides,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectProperties:
    """Build and launch defaults for a project."""

    output_directory: str = "bin"
    default_compiler_profile_id: UUID | None = None
    default_launch_configuration_id: UUID | None = None

    def __post_init__(self) -> None:
        """Normalize and validate project properties."""

        output_directory = _require_relative_project_path(
            self.output_directory,
            "Project output directory",
        )

        if (
            self.default_compiler_profile_id is not None
            and not isinstance(
                self.default_compiler_profile_id,
                UUID,
            )
        ):
            raise TypeError(
                "Default compiler profile ID must be a UUID or None."
            )

        if (
            self.default_launch_configuration_id is not None
            and not isinstance(
                self.default_launch_configuration_id,
                UUID,
            )
        ):
            raise TypeError(
                "Default launch configuration ID must be a UUID "
                "or None."
            )

        object.__setattr__(
            self,
            "output_directory",
            output_directory,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Project:
    """Complete persisted state of one OpenCobol2 project."""

    schema_version: int = CURRENT_PROJECT_SCHEMA_VERSION
    project_id: UUID
    name: str
    root_path: Path
    properties: ProjectProperties = field(
        default_factory=ProjectProperties,
    )
    excluded_patterns: tuple[str, ...] = ()
    environment_overrides: Mapping[str, str] = field(
        default_factory=dict,
    )
    virtual_folders: tuple[VirtualFolder, ...] = ()
    linked_files: tuple[LinkedFile, ...] = ()
    tasks: tuple[ProjectTask, ...] = ()
    launch_configurations: tuple[LaunchConfiguration, ...] = ()

    def __post_init__(self) -> None:
        """Validate cross-referential project state."""

        if (
            not isinstance(
                self.schema_version,
                int,
            )
            or isinstance(
                self.schema_version,
                bool,
            )
        ):
            raise TypeError(
                "Project schema version must be an integer."
            )

        if self.schema_version != CURRENT_PROJECT_SCHEMA_VERSION:
            # A Project instance always represents the current,
            # fully-migrated state -- any version migration belongs
            # at the raw-JSON decode layer (ProjectStorage), which
            # stamps the constructed Project with the current version
            # rather than handing this constructor a stale one. If
            # this weren't enforced, a project could be saved with a
            # schema_version its own loader immediately rejects.
            raise ValueError(
                "Project schema version must be "
                f"{CURRENT_PROJECT_SCHEMA_VERSION}, got "
                f"{self.schema_version}."
            )

        if not isinstance(
            self.project_id,
            UUID,
        ):
            raise TypeError(
                "Project ID must be a UUID."
            )

        name = _require_non_empty_string(
            self.name,
            "Project name",
        )
        root_path = Path(
            self.root_path,
        )

        if not str(
            root_path,
        ):
            raise ValueError(
                "Project root path must not be empty."
            )

        if not isinstance(
            self.properties,
            ProjectProperties,
        ):
            raise TypeError(
                "Project properties must be ProjectProperties."
            )

        excluded_patterns = _require_string_tuple(
            self.excluded_patterns,
            "Project excluded patterns",
            allow_empty_items=False,
        )
        environment_overrides = _require_string_mapping(
            self.environment_overrides,
            "Project environment overrides",
        )

        virtual_folders = tuple(
            self.virtual_folders,
        )

        if not all(
            isinstance(
                folder,
                VirtualFolder,
            )
            for folder in virtual_folders
        ):
            raise TypeError(
                "Project virtual folders must contain "
                "VirtualFolder instances."
            )

        linked_files = tuple(
            self.linked_files,
        )

        if not all(
            isinstance(
                linked_file,
                LinkedFile,
            )
            for linked_file in linked_files
        ):
            raise TypeError(
                "Project linked files must contain LinkedFile "
                "instances."
            )

        linked_file_ids = tuple(
            linked_file.linked_file_id
            for linked_file in linked_files
        )

        if len(
            set(
                linked_file_ids,
            ),
        ) != len(
            linked_file_ids,
        ):
            raise ValueError(
                "Linked file IDs must be unique."
            )

        folder_ids = _collect_virtual_folder_ids(
            virtual_folders,
        )

        if len(
            set(
                folder_ids,
            ),
        ) != len(
            folder_ids,
        ):
            raise ValueError(
                "Virtual folder IDs must be unique."
            )

        referenced_linked_file_ids = (
            _collect_referenced_linked_file_ids(
                virtual_folders,
            )
        )

        if not referenced_linked_file_ids.issubset(
            set(
                linked_file_ids,
            ),
        ):
            raise ValueError(
                "Virtual folders reference a linked file that "
                "is not part of the project."
            )

        tasks = tuple(
            self.tasks,
        )

        if not all(
            isinstance(
                task,
                ProjectTask,
            )
            for task in tasks
        ):
            raise TypeError(
                "Project tasks must contain ProjectTask instances."
            )

        task_ids = tuple(
            task.task_id
            for task in tasks
        )

        if len(
            set(
                task_ids,
            ),
        ) != len(
            task_ids,
        ):
            raise ValueError(
                "Project task IDs must be unique."
            )

        task_names = tuple(
            task.name
            for task in tasks
        )

        if len(
            set(
                task_names,
            ),
        ) != len(
            task_names,
        ):
            raise ValueError(
                "Project task names must be unique."
            )

        launch_configurations = tuple(
            self.launch_configurations,
        )

        if not all(
            isinstance(
                launch_configuration,
                LaunchConfiguration,
            )
            for launch_configuration in launch_configurations
        ):
            raise TypeError(
                "Project launch configurations must contain "
                "LaunchConfiguration instances."
            )

        launch_configuration_ids = tuple(
            launch_configuration.launch_configuration_id
            for launch_configuration in launch_configurations
        )

        if len(
            set(
                launch_configuration_ids,
            ),
        ) != len(
            launch_configuration_ids,
        ):
            raise ValueError(
                "Launch configuration IDs must be unique."
            )

        launch_configuration_names = tuple(
            launch_configuration.name
            for launch_configuration in launch_configurations
        )

        if len(
            set(
                launch_configuration_names,
            ),
        ) != len(
            launch_configuration_names,
        ):
            raise ValueError(
                "Launch configuration names must be unique."
            )

        if (
            self.properties.default_launch_configuration_id
            is not None
            and self.properties.default_launch_configuration_id
            not in launch_configuration_ids
        ):
            raise ValueError(
                "Default launch configuration ID must reference "
                "an existing launch configuration."
            )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "root_path",
            root_path,
        )
        object.__setattr__(
            self,
            "excluded_patterns",
            excluded_patterns,
        )
        object.__setattr__(
            self,
            "environment_overrides",
            environment_overrides,
        )
        object.__setattr__(
            self,
            "virtual_folders",
            virtual_folders,
        )
        object.__setattr__(
            self,
            "linked_files",
            linked_files,
        )
        object.__setattr__(
            self,
            "tasks",
            tasks,
        )
        object.__setattr__(
            self,
            "launch_configurations",
            launch_configurations,
        )

    def get_task(
        self,
        task_id: UUID,
    ) -> ProjectTask | None:
        """Return a project task by ID."""

        for task in self.tasks:
            if task.task_id == task_id:
                return task

        return None

    def get_launch_configuration(
        self,
        launch_configuration_id: UUID,
    ) -> LaunchConfiguration | None:
        """Return a launch configuration by ID."""

        for launch_configuration in self.launch_configurations:
            if (
                launch_configuration.launch_configuration_id
                == launch_configuration_id
            ):
                return launch_configuration

        return None

    def get_linked_file(
        self,
        linked_file_id: UUID,
    ) -> LinkedFile | None:
        """Return a linked file by ID."""

        for linked_file in self.linked_files:
            if linked_file.linked_file_id == linked_file_id:
                return linked_file

        return None


def create_project(
    *,
    name: str,
    root_path: Path | str,
) -> Project:
    """Create a new project with a freshly generated identity."""

    return Project(
        project_id=uuid4(),
        name=name,
        root_path=Path(
            root_path,
        ),
    )


def _collect_virtual_folder_ids(
    folders: Sequence[VirtualFolder],
) -> list[UUID]:
    """Recursively collect every virtual folder ID in a tree."""

    ids: list[UUID] = []

    for folder in folders:
        ids.append(
            folder.folder_id,
        )
        ids.extend(
            _collect_virtual_folder_ids(
                folder.virtual_folders,
            ),
        )

    return ids


def _collect_referenced_linked_file_ids(
    folders: Sequence[VirtualFolder],
) -> set[UUID]:
    """Recursively collect every linked file ID referenced in a tree."""

    referenced: set[UUID] = set()

    for folder in folders:
        referenced.update(
            folder.linked_file_ids,
        )
        referenced.update(
            _collect_referenced_linked_file_ids(
                folder.virtual_folders,
            ),
        )

    return referenced


def _require_non_empty_string(
    value: str,
    name: str,
) -> str:
    """Require and normalize one non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized_value


def _require_relative_project_path(
    value: str,
    name: str,
) -> str:
    """Require a project-relative, non-traversing path string."""

    normalized_value = _require_non_empty_string(
        value,
        name,
    )
    path = Path(
        normalized_value,
    )

    if (
        path.is_absolute()
        or path.drive
        or normalized_value.startswith(
            (
                "/",
                "\\",
            ),
        )
    ):
        # PureWindowsPath.is_absolute() requires *both* a drive and a
        # root -- a drive-relative string like "E:payload/nc.exe" has
        # a drive but no root, so is_absolute() is False even though
        # joining it onto another path discards that path entirely
        # (PureWindowsPath("C:/proj") / "E:payload" == "E:payload").
        # Checking path.drive directly closes that gap.
        raise ValueError(
            f"{name} must be relative."
        )

    if ".." in path.parts:
        raise ValueError(
            f"{name} must not traverse outside the project."
        )

    return normalized_value


def _require_string_tuple(
    values: Sequence[str],
    name: str,
    *,
    allow_empty_items: bool = True,
) -> tuple[str, ...]:
    """Require a sequence of strings."""

    if isinstance(
        values,
        (
            str,
            bytes,
        ),
    ):
        raise TypeError(
            f"{name} must be a sequence of strings."
        )

    if not isinstance(
        values,
        Sequence,
    ):
        raise TypeError(
            f"{name} must be a sequence of strings."
        )

    normalized_values: list[str] = []

    for value in values:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} must contain only strings."
            )

        if not allow_empty_items and not value.strip():
            raise ValueError(
                f"{name} must not contain empty values."
            )

        normalized_values.append(
            value,
        )

    return tuple(
        normalized_values,
    )


def _require_string_mapping(
    values: Mapping[str, str],
    name: str,
) -> dict[str, str]:
    """Require a mapping containing string keys and values."""

    if not isinstance(
        values,
        Mapping,
    ):
        raise TypeError(
            f"{name} must be a mapping."
        )

    normalized_values: dict[str, str] = {}
    seen_folded_keys: dict[str, str] = {}

    for key, value in values.items():
        if not isinstance(
            key,
            str,
        ):
            raise TypeError(
                f"{name} keys must be strings."
            )

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{name} values must be strings."
            )

        # Environment variable names are case-insensitive on some
        # platforms (Windows); accepting both "PATH" and "Path" in
        # the same override map is an unresolvable ambiguity, not a
        # legitimate use case, so reject it here rather than letting
        # it surface later as unpredictable subprocess behavior.
        folded_key = key.casefold()

        if folded_key in seen_folded_keys:
            raise ValueError(
                f"{name} keys must not collide case-insensitively: "
                f"{seen_folded_keys[folded_key]!r} and {key!r}."
            )

        seen_folded_keys[folded_key] = key
        normalized_values[key] = value

    return normalized_values
