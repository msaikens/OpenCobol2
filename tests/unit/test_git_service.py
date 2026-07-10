"""Unit tests for local Git repository services."""

from pathlib import Path

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
    GitCommandTimedOutError,
    GitExecutableUnavailableError,
    GitRepositoryNotFoundError,
    GitService,
)


def test_discover_repository_returns_git_worktree_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[
        tuple[str, ...]
    ] = []

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        commands.append(
            command,
        )

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.COMPLETED,
            return_code=0,
            stdout="/source/project\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    root = service.discover_repository(
        "/source/project/src",
    )

    assert root == Path(
        "/source/project"
    )
    assert commands == [
        (
            "git",
            "--no-optional-locks",
            "rev-parse",
            "--show-toplevel",
        ),
    ]


def test_discover_repository_uses_configured_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_command

        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        captured_command = command

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.COMPLETED,
            return_code=0,
            stdout="/source/project\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService(
        executable_path=r"C:\Program Files\Git\cmd\git.exe",
    )

    service.discover_repository(
        "/source/project",
    )

    assert captured_command is not None
    assert (
        captured_command[
            0
        ]
        == r"C:\Program Files\Git\cmd\git.exe"
    )


def test_get_status_discovers_root_then_reads_porcelain_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[
        tuple[str, ...]
    ] = []

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        commands.append(
            command,
        )

        if "rev-parse" in command:
            stdout = "/source/project\n"
        else:
            stdout = (
                "# branch.oid abc123\0"
                "# branch.head main\0"
                "? PAYROLL.cob\0"
            )

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.COMPLETED,
            return_code=0,
            stdout=stdout,
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    status = service.get_status(
        "/source/project/src",
    )

    assert status.repository_root == Path(
        "/source/project"
    )
    assert status.branch_name == "main"
    assert len(
        status.changes,
    ) == 1
    assert status.changes[
        0
    ].path == Path(
        "PAYROLL.cob"
    )

    assert commands == [
        (
            "git",
            "--no-optional-locks",
            "rev-parse",
            "--show-toplevel",
        ),
        (
            "git",
            "--no-optional-locks",
            "status",
            "--porcelain=v2",
            "--branch",
            "-z",
        ),
    ]


def test_non_repository_path_raises_repository_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.COMPLETED,
            return_code=128,
            stderr="fatal: not a git repository",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitRepositoryNotFoundError,
    ):
        service.discover_repository(
            "/source/not-a-repository",
        )


def test_missing_git_executable_raises_explicit_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.FAILED_TO_START,
            error_message="Unable to start Git: missing",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitExecutableUnavailableError,
        match="missing",
    ):
        service.discover_repository(
            "/source/project",
        )


def test_git_timeout_raises_explicit_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.TIMED_OUT,
            error_message="Git command timed out.",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandTimedOutError,
    ):
        service.discover_repository(
            "/source/project",
        )


def test_failed_status_command_preserves_git_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal call_count

        call_count += 1

        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        if call_count == 1:
            return GitCommandResult(
                command=command,
                status=GitCommandExecutionStatus.COMPLETED,
                return_code=0,
                stdout="/source/project\n",
            )

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.COMPLETED,
            return_code=1,
            stderr="status failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="status failed",
    ) as error:
        service.get_status(
            "/source/project",
        )

    assert error.value.result.return_code == 1


def test_environment_overrides_are_merged_with_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_environment: object = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_environment

        captured_environment = kwargs[
            "environment"
        ]

        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.COMPLETED,
            return_code=0,
            stdout="/source/project\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    monkeypatch.setenv(
        "OPENCOBOL2_EXISTING_TEST_VARIABLE",
        "existing",
    )

    service = GitService(
        environment_overrides={
            "OPENCOBOL2_GIT_TEST_VARIABLE": "override",
        },
    )

    service.discover_repository(
        "/source/project",
    )

    assert isinstance(
        captured_environment,
        dict,
    )
    assert (
        captured_environment[
            "OPENCOBOL2_EXISTING_TEST_VARIABLE"
        ]
        == "existing"
    )
    assert (
        captured_environment[
            "OPENCOBOL2_GIT_TEST_VARIABLE"
        ]
        == "override"
    )


def test_git_service_rejects_boolean_timeout() -> None:
    with pytest.raises(
        TypeError,
        match="must be numeric",
    ):
        GitService(
            timeout_seconds=True,
        )