"""Application service for a persisted OpenCobol2 project."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

from opencobol2.project.models import (
    LaunchConfiguration,
    LinkedFile,
    Project,
    ProjectProperties,
    ProjectTask,
    VirtualFolder,
)
from opencobol2.project.storage import (
    ProjectStorage,
)


class VirtualFolderNotFoundError(LookupError):
    """Raised when a referenced virtual folder does not exist."""


class LinkedFileNotFoundError(LookupError):
    """Raised when a referenced linked file does not exist."""


class ProjectTaskNotFoundError(LookupError):
    """Raised when a referenced project task does not exist."""


class LaunchConfigurationNotFoundError(LookupError):
    """Raised when a referenced launch configuration does not exist."""


class ProjectService:
    """Owns the current persisted project snapshot."""

    __slots__ = (
        "_storage",
        "_current",
    )

    def __init__(
        self,
        storage: ProjectStorage,
        *,
        project: Project | None = None,
    ) -> None:
        """Initialize the project service, opening or creating a project."""

        self._storage = storage

        if project is not None:
            if not isinstance(
                project,
                Project,
            ):
                raise TypeError(
                    "Project must be Project."
                )

            self._storage.save(
                project,
            )
            self._current = project
        else:
            self._current = storage.load()

    @property
    def storage(
        self,
    ) -> ProjectStorage:
        """Return the project persistence service."""

        return self._storage

    @property
    def current(
        self,
    ) -> Project:
        """Return the current project snapshot."""

        return self._current

    def reload(
        self,
    ) -> Project:
        """Reload the persisted project and replace the current snapshot."""

        project = self._storage.load()
        self._current = project

        return project

    def apply(
        self,
        project: Project,
    ) -> Project:
        """Persist and apply a complete project snapshot."""

        if not isinstance(
            project,
            Project,
        ):
            raise TypeError(
                "Project must be Project."
            )

        self._storage.save(
            project,
        )
        self._current = project

        return project

    def update_properties(
        self,
        properties: ProjectProperties,
    ) -> Project:
        """Persist replacement build and launch default properties."""

        if not isinstance(
            properties,
            ProjectProperties,
        ):
            raise TypeError(
                "Project properties must be ProjectProperties."
            )

        return self.apply(
            replace(
                self._current,
                properties=properties,
            ),
        )

    def update_excluded_patterns(
        self,
        patterns: Sequence[str],
    ) -> Project:
        """Persist replacement excluded file patterns."""

        return self.apply(
            replace(
                self._current,
                excluded_patterns=tuple(
                    patterns,
                ),
            ),
        )

    def update_environment_overrides(
        self,
        environment_overrides: Mapping[str, str],
    ) -> Project:
        """Persist replacement project-level environment overrides."""

        return self.apply(
            replace(
                self._current,
                environment_overrides=dict(
                    environment_overrides,
                ),
            ),
        )

    def add_virtual_folder(
        self,
        name: str,
        *,
        parent_id: UUID | None = None,
    ) -> Project:
        """Add a new virtual folder and return the updated project."""

        new_folder = VirtualFolder(
            folder_id=uuid4(),
            name=name,
        )

        if parent_id is None:
            updated_folders = (
                self._current.virtual_folders
                + (new_folder,)
            )
        else:
            (
                updated_folders,
                found,
            ) = _insert_virtual_folder(
                self._current.virtual_folders,
                parent_id,
                new_folder,
            )

            if not found:
                raise VirtualFolderNotFoundError(
                    f"Virtual folder does not exist: {parent_id}"
                )

        return self.apply(
            replace(
                self._current,
                virtual_folders=updated_folders,
            ),
        )

    def remove_virtual_folder(
        self,
        folder_id: UUID,
    ) -> Project:
        """Remove a virtual folder and return the updated project."""

        (
            updated_folders,
            found,
        ) = _remove_virtual_folder(
            self._current.virtual_folders,
            folder_id,
        )

        if not found:
            raise VirtualFolderNotFoundError(
                f"Virtual folder does not exist: {folder_id}"
            )

        return self.apply(
            replace(
                self._current,
                virtual_folders=updated_folders,
            ),
        )

    def add_linked_file(
        self,
        display_name: str,
        target_path: Path | str,
    ) -> Project:
        """Add a new linked file and return the updated project."""

        linked_file = LinkedFile(
            linked_file_id=uuid4(),
            display_name=display_name,
            target_path=Path(
                target_path,
            ),
        )

        return self.apply(
            replace(
                self._current,
                linked_files=(
                    self._current.linked_files
                    + (linked_file,)
                ),
            ),
        )

    def remove_linked_file(
        self,
        linked_file_id: UUID,
    ) -> Project:
        """Remove a linked file and return the updated project."""

        if (
            self._current.get_linked_file(
                linked_file_id,
            )
            is None
        ):
            raise LinkedFileNotFoundError(
                f"Linked file does not exist: {linked_file_id}"
            )

        remaining = tuple(
            linked_file
            for linked_file in self._current.linked_files
            if linked_file.linked_file_id != linked_file_id
        )

        return self.apply(
            replace(
                self._current,
                linked_files=remaining,
            ),
        )

    def add_task(
        self,
        name: str,
        executable: str,
        *,
        arguments: Sequence[str] = (),
        working_directory: str | None = None,
        environment_overrides: Mapping[str, str] | None = None,
    ) -> Project:
        """Add a new project task and return the updated project."""

        task = ProjectTask(
            task_id=uuid4(),
            name=name,
            executable=executable,
            arguments=tuple(
                arguments,
            ),
            working_directory=working_directory,
            environment_overrides=dict(
                environment_overrides or {},
            ),
        )

        return self.apply(
            replace(
                self._current,
                tasks=(
                    self._current.tasks
                    + (task,)
                ),
            ),
        )

    def remove_task(
        self,
        task_id: UUID,
    ) -> Project:
        """Remove a project task and return the updated project."""

        if self._current.get_task(
            task_id,
        ) is None:
            raise ProjectTaskNotFoundError(
                f"Project task does not exist: {task_id}"
            )

        remaining = tuple(
            task
            for task in self._current.tasks
            if task.task_id != task_id
        )

        return self.apply(
            replace(
                self._current,
                tasks=remaining,
            ),
        )

    def add_launch_configuration(
        self,
        name: str,
        executable_path: str,
        *,
        arguments: Sequence[str] = (),
        working_directory: str | None = None,
        environment_overrides: Mapping[str, str] | None = None,
    ) -> Project:
        """Add a new launch configuration and return the updated project."""

        launch_configuration = LaunchConfiguration(
            launch_configuration_id=uuid4(),
            name=name,
            executable_path=executable_path,
            arguments=tuple(
                arguments,
            ),
            working_directory=working_directory,
            environment_overrides=dict(
                environment_overrides or {},
            ),
        )

        return self.apply(
            replace(
                self._current,
                launch_configurations=(
                    self._current.launch_configurations
                    + (launch_configuration,)
                ),
            ),
        )

    def remove_launch_configuration(
        self,
        launch_configuration_id: UUID,
    ) -> Project:
        """Remove a launch configuration and return the updated project."""

        if (
            self._current.get_launch_configuration(
                launch_configuration_id,
            )
            is None
        ):
            raise LaunchConfigurationNotFoundError(
                "Launch configuration does not exist: "
                f"{launch_configuration_id}"
            )

        remaining = tuple(
            launch_configuration
            for launch_configuration in (
                self._current.launch_configurations
            )
            if (
                launch_configuration.launch_configuration_id
                != launch_configuration_id
            )
        )

        properties = self._current.properties

        if (
            properties.default_launch_configuration_id
            == launch_configuration_id
        ):
            properties = replace(
                properties,
                default_launch_configuration_id=None,
            )

        return self.apply(
            replace(
                self._current,
                launch_configurations=remaining,
                properties=properties,
            ),
        )


def _insert_virtual_folder(
    folders: tuple[VirtualFolder, ...],
    parent_id: UUID,
    new_folder: VirtualFolder,
) -> tuple[tuple[VirtualFolder, ...], bool]:
    """Recursively insert a virtual folder under a parent by ID."""

    updated_folders: list[VirtualFolder] = []
    found = False

    for folder in folders:
        if folder.folder_id == parent_id:
            folder = replace(
                folder,
                virtual_folders=(
                    folder.virtual_folders
                    + (new_folder,)
                ),
            )
            found = True
        elif folder.virtual_folders:
            (
                new_children,
                child_found,
            ) = _insert_virtual_folder(
                folder.virtual_folders,
                parent_id,
                new_folder,
            )

            if child_found:
                folder = replace(
                    folder,
                    virtual_folders=new_children,
                )
                found = True

        updated_folders.append(
            folder,
        )

    return (
        tuple(
            updated_folders,
        ),
        found,
    )


def _remove_virtual_folder(
    folders: tuple[VirtualFolder, ...],
    folder_id: UUID,
) -> tuple[tuple[VirtualFolder, ...], bool]:
    """Recursively remove a virtual folder by ID."""

    updated_folders: list[VirtualFolder] = []
    found = False

    for folder in folders:
        if folder.folder_id == folder_id:
            found = True
            continue

        if folder.virtual_folders:
            (
                new_children,
                child_found,
            ) = _remove_virtual_folder(
                folder.virtual_folders,
                folder_id,
            )

            if child_found:
                folder = replace(
                    folder,
                    virtual_folders=new_children,
                )
                found = True

        updated_folders.append(
            folder,
        )

    return (
        tuple(
            updated_folders,
        ),
        found,
    )
