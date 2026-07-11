"""Application service for running project tasks and launch configurations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
from uuid import UUID

from opencobol2.project import (
    Project,
    TaskRunResult,
    invoke_task_process,
)
from opencobol2.project.service import (
    LaunchConfigurationNotFoundError,
    ProjectTaskNotFoundError,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectTaskRunnerService:
    """Runs configured project tasks and launch configurations."""

    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        """Validate the configured process timeout."""

        if (
            not isinstance(
                self.timeout_seconds,
                (
                    int,
                    float,
                ),
            )
            or isinstance(
                self.timeout_seconds,
                bool,
            )
        ):
            raise TypeError(
                "Task runner timeout must be numeric."
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "Task runner timeout must be greater than zero."
            )

    def run_task(
        self,
        project: Project,
        task_id: UUID,
    ) -> TaskRunResult:
        """Run one configured project task."""

        task = project.get_task(
            task_id,
        )

        if task is None:
            raise ProjectTaskNotFoundError(
                f"Project task does not exist: {task_id}"
            )

        return invoke_task_process(
            command=(
                task.executable,
                *task.arguments,
            ),
            run_id=task.task_id,
            timeout_seconds=self.timeout_seconds,
            working_directory=_resolve_working_directory(
                project,
                task.working_directory,
            ),
            environment=_merge_environment(
                project.environment_overrides,
                task.environment_overrides,
            ),
        )

    def run_launch_configuration(
        self,
        project: Project,
        launch_configuration_id: UUID,
    ) -> TaskRunResult:
        """Run one configured project launch configuration."""

        launch_configuration = project.get_launch_configuration(
            launch_configuration_id,
        )

        if launch_configuration is None:
            raise LaunchConfigurationNotFoundError(
                "Launch configuration does not exist: "
                f"{launch_configuration_id}"
            )

        executable = str(
            project.root_path
            / launch_configuration.executable_path,
        )

        return invoke_task_process(
            command=(
                executable,
                *launch_configuration.arguments,
            ),
            run_id=(
                launch_configuration.launch_configuration_id
            ),
            timeout_seconds=self.timeout_seconds,
            working_directory=_resolve_working_directory(
                project,
                launch_configuration.working_directory,
            ),
            environment=_merge_environment(
                project.environment_overrides,
                launch_configuration.environment_overrides,
            ),
        )


def _resolve_working_directory(
    project: Project,
    relative_working_directory: str | None,
) -> Path:
    """Resolve a task or launch working directory against the project root."""

    if relative_working_directory is None:
        return project.root_path

    return project.root_path / relative_working_directory


def _merge_environment(
    project_overrides: Mapping[str, str],
    local_overrides: Mapping[str, str],
) -> dict[str, str]:
    """Layer ambient, project, and task/launch environment overrides."""

    environment = dict(
        os.environ,
    )
    environment.update(
        project_overrides,
    )
    environment.update(
        local_overrides,
    )

    return environment
