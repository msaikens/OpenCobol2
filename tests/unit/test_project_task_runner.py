"""Unit tests for the project task/launch runner service."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from opencobol2.project import (
    LaunchConfiguration,
    Project,
    ProjectTask,
    TaskExecutionStatus,
    TaskRunResult,
    create_project,
)
from opencobol2.services import project as project_service_module
from opencobol2.services.project import (
    ProjectTaskRunnerService,
)
from opencobol2.project.service import (
    LaunchConfigurationNotFoundError,
    ProjectTaskNotFoundError,
)


def _completed_result(
    run_id: UUID,
    command: tuple[str, ...],
) -> TaskRunResult:
    """Create one completed task run result."""

    return TaskRunResult(
        run_id=run_id,
        command=command,
        status=TaskExecutionStatus.COMPLETED,
        return_code=0,
        stdout="ok",
    )


def _project_with_task(
    root_path: Path,
    **task_overrides: object,
) -> tuple[Project, ProjectTask]:
    """Build a project with one task attached."""

    project = create_project(
        name="Demo",
        root_path=root_path,
    )
    task_defaults: dict[str, object] = {
        "task_id": uuid4(),
        "name": "Build",
        "executable": "cobc",
        "arguments": ("-x", "main.cob"),
    }
    task_defaults.update(task_overrides)
    task = ProjectTask(**task_defaults)

    from dataclasses import replace

    project = replace(
        project,
        tasks=(task,),
    )

    return project, task


def _project_with_launch(
    root_path: Path,
    **launch_overrides: object,
) -> tuple[Project, LaunchConfiguration]:
    """Build a project with one launch configuration attached."""

    project = create_project(
        name="Demo",
        root_path=root_path,
    )
    launch_defaults: dict[str, object] = {
        "launch_configuration_id": uuid4(),
        "name": "Run",
        "executable_path": "bin/main",
    }
    launch_defaults.update(launch_overrides)
    launch_configuration = LaunchConfiguration(
        **launch_defaults,
    )

    from dataclasses import replace

    project = replace(
        project,
        launch_configurations=(launch_configuration,),
    )

    return project, launch_configuration


def test_run_task_invokes_expected_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    def invoke_task_process(
        **kwargs: object,
    ) -> TaskRunResult:
        captured_kwargs.update(kwargs)

        return _completed_result(
            kwargs["run_id"],
            kwargs["command"],
        )

    monkeypatch.setattr(
        project_service_module,
        "invoke_task_process",
        invoke_task_process,
    )

    project, task = _project_with_task(tmp_path)
    service = ProjectTaskRunnerService()

    result = service.run_task(project, task.task_id)

    assert result.succeeded is True
    assert captured_kwargs["command"] == ("cobc", "-x", "main.cob")
    # run_id must be a fresh per-invocation identifier, not the task's
    # own permanent ID -- otherwise two concurrent runs of the same
    # task would be indistinguishable to any caller correlating
    # output or attempting to cancel one of them.
    assert isinstance(captured_kwargs["run_id"], UUID)
    assert captured_kwargs["run_id"] != task.task_id
    assert captured_kwargs["working_directory"] == tmp_path


def test_run_task_mints_a_distinct_run_id_per_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_run_ids: list[UUID] = []

    def invoke_task_process(
        **kwargs: object,
    ) -> TaskRunResult:
        captured_run_ids.append(kwargs["run_id"])

        return _completed_result(
            kwargs["run_id"],
            kwargs["command"],
        )

    monkeypatch.setattr(
        project_service_module,
        "invoke_task_process",
        invoke_task_process,
    )

    project, task = _project_with_task(tmp_path)
    service = ProjectTaskRunnerService()

    service.run_task(project, task.task_id)
    service.run_task(project, task.task_id)

    assert len(captured_run_ids) == 2
    assert captured_run_ids[0] != captured_run_ids[1]


def test_run_task_resolves_relative_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    def invoke_task_process(
        **kwargs: object,
    ) -> TaskRunResult:
        captured_kwargs.update(kwargs)

        return _completed_result(
            kwargs["run_id"],
            kwargs["command"],
        )

    monkeypatch.setattr(
        project_service_module,
        "invoke_task_process",
        invoke_task_process,
    )

    project, task = _project_with_task(
        tmp_path,
        working_directory="src",
    )
    service = ProjectTaskRunnerService()
    service.run_task(project, task.task_id)

    assert captured_kwargs["working_directory"] == tmp_path / "src"


def test_run_task_merges_environment_with_project_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    captured_kwargs: dict[str, object] = {}

    def invoke_task_process(
        **kwargs: object,
    ) -> TaskRunResult:
        captured_kwargs.update(kwargs)

        return _completed_result(
            kwargs["run_id"],
            kwargs["command"],
        )

    monkeypatch.setattr(
        project_service_module,
        "invoke_task_process",
        invoke_task_process,
    )

    project, task = _project_with_task(
        tmp_path,
        environment_overrides={"COB_COPY_DIR": "task-copy"},
    )
    project = replace(
        project,
        environment_overrides={
            "COB_CONFIG_DIR": "project-config",
            "COB_COPY_DIR": "project-copy",
        },
    )

    service = ProjectTaskRunnerService()
    service.run_task(project, task.task_id)

    environment = captured_kwargs["environment"]
    assert environment["COB_CONFIG_DIR"] == "project-config"
    assert environment["COB_COPY_DIR"] == "task-copy"


def test_run_task_environment_merge_is_case_insensitive_on_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """os.environ is case-insensitive on Windows, but dict(os.environ)
    is not -- an override differing only in case from an ambient
    variable must replace it, not sit alongside it as a second,
    differently-cased entry whose precedence is otherwise undefined."""

    from dataclasses import replace

    monkeypatch.setattr(
        project_service_module.os,
        "name",
        "nt",
    )
    monkeypatch.setenv(
        "Path",
        "C:\\ambient",
    )

    captured_kwargs: dict[str, object] = {}

    def invoke_task_process(
        **kwargs: object,
    ) -> TaskRunResult:
        captured_kwargs.update(kwargs)

        return _completed_result(
            kwargs["run_id"],
            kwargs["command"],
        )

    monkeypatch.setattr(
        project_service_module,
        "invoke_task_process",
        invoke_task_process,
    )

    project, task = _project_with_task(
        tmp_path,
        environment_overrides={"PATH": "C:\\override"},
    )

    service = ProjectTaskRunnerService()
    service.run_task(project, task.task_id)

    environment = captured_kwargs["environment"]
    matching_keys = [
        key for key in environment if key.casefold() == "path"
    ]
    assert matching_keys == ["PATH"]
    assert environment["PATH"] == "C:\\override"


def test_run_task_environment_merge_stays_case_sensitive_off_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a platform where environment variables really are
    case-sensitive, PATH and Path must remain two distinct entries --
    collapsing them there would be the actual regression."""

    from dataclasses import replace

    monkeypatch.setattr(
        project_service_module.os,
        "name",
        "posix",
    )
    monkeypatch.setenv(
        "PATH",
        "/ambient",
    )

    captured_kwargs: dict[str, object] = {}

    def invoke_task_process(
        **kwargs: object,
    ) -> TaskRunResult:
        captured_kwargs.update(kwargs)

        return _completed_result(
            kwargs["run_id"],
            kwargs["command"],
        )

    monkeypatch.setattr(
        project_service_module,
        "invoke_task_process",
        invoke_task_process,
    )

    project, task = _project_with_task(
        tmp_path,
        environment_overrides={"Path": "/override"},
    )

    service = ProjectTaskRunnerService()
    service.run_task(project, task.task_id)

    environment = captured_kwargs["environment"]
    assert environment["PATH"] == "/ambient"
    assert environment["Path"] == "/override"


def test_run_task_rejects_unknown_task_id(
    tmp_path: Path,
) -> None:
    project = create_project(name="Demo", root_path=tmp_path)
    service = ProjectTaskRunnerService()

    with pytest.raises(ProjectTaskNotFoundError):
        service.run_task(project, uuid4())


def test_run_launch_configuration_invokes_expected_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    def invoke_task_process(
        **kwargs: object,
    ) -> TaskRunResult:
        captured_kwargs.update(kwargs)

        return _completed_result(
            kwargs["run_id"],
            kwargs["command"],
        )

    monkeypatch.setattr(
        project_service_module,
        "invoke_task_process",
        invoke_task_process,
    )

    project, launch_configuration = _project_with_launch(
        tmp_path,
        arguments=("--verbose",),
    )
    service = ProjectTaskRunnerService()

    result = service.run_launch_configuration(
        project,
        launch_configuration.launch_configuration_id,
    )

    assert result.succeeded is True
    assert captured_kwargs["command"] == (
        str(tmp_path / "bin/main"),
        "--verbose",
    )
    assert captured_kwargs["working_directory"] == tmp_path


def test_run_launch_configuration_rejects_unknown_id(
    tmp_path: Path,
) -> None:
    project = create_project(name="Demo", root_path=tmp_path)
    service = ProjectTaskRunnerService()

    with pytest.raises(LaunchConfigurationNotFoundError):
        service.run_launch_configuration(project, uuid4())


def test_service_rejects_non_positive_timeout() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        ProjectTaskRunnerService(timeout_seconds=0)


def test_service_rejects_non_numeric_timeout() -> None:
    with pytest.raises(
        TypeError,
        match="must be numeric",
    ):
        ProjectTaskRunnerService(
            timeout_seconds="30",  # type: ignore[arg-type]
        )
