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
    GitRepositoryPathError,
    GitService,
)


def _completed_result(
    command: tuple[str, ...],
    *,
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> GitCommandResult:
    """Create one completed Git command result."""

    return GitCommandResult(
        command=command,
        status=GitCommandExecutionStatus.COMPLETED,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
    )


def _command_from_kwargs(
    kwargs: dict[str, object],
) -> tuple[str, ...]:
    """Extract and validate a mocked Git command."""

    command = kwargs[
        "command"
    ]

    assert isinstance(
        command,
        tuple,
    )

    return command


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

        return _completed_result(
            command,
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

        return _completed_result(
            command,
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


def test_set_executable_path_changes_future_invocations(
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
        captured_command = command

        return _completed_result(
            command,
            stdout="/source/project\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    assert service.executable_path == "git"

    service.set_executable_path(
        r"C:\Program Files\Git\cmd\git.exe",
    )
    assert (
        service.executable_path
        == r"C:\Program Files\Git\cmd\git.exe"
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


def test_set_executable_path_rejects_empty_value() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="Git executable path must not be empty",
    ):
        service.set_executable_path(
            "   ",
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

        return _completed_result(
            command,
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


def test_stage_paths_uses_pathspec_separator_and_refreshes_status(
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
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[
            1
        ] == "add":
            return _completed_result(
                command,
            )

        return _completed_result(
            command,
            stdout=(
                "# branch.oid abc123\0"
                "# branch.head main\0"
                "1 M. N... 100644 100644 100644 "
                "abc abc --strange.cob\0"
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    status = service.stage_paths(
        "/source/project",
        (
            "--strange.cob",
            "src/PAYROLL.cob",
        ),
    )

    assert commands[
        1
    ] == (
        "git",
        "add",
        "--",
        "--strange.cob",
        "src/PAYROLL.cob",
    )
    assert commands[
        2
    ][
        1:
    ] == (
        "--no-optional-locks",
        "status",
        "--porcelain=v2",
        "--branch",
        "-z",
    )
    assert status.has_staged_changes is True


def test_stage_all_uses_git_add_all_and_refreshes_status(
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
        elif command[
            1
        ] == "add":
            stdout = ""
        else:
            stdout = (
                "# branch.oid abc123\0"
                "# branch.head main\0"
            )

        return _completed_result(
            command,
            stdout=stdout,
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    status = service.stage_all(
        "/source/project",
    )

    assert commands[
        1
    ] == (
        "git",
        "add",
        "--all",
    )
    assert len(
        commands,
    ) == 3
    assert status.clean is True


def test_unstage_paths_uses_restore_staged_when_head_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[
        tuple[str, ...]
    ] = []
    status_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal status_reads

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
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if "status" in command:
            status_reads += 1

            stdout = (
                "# branch.oid abc123\0"
                "# branch.head main\0"
            )

            if status_reads == 1:
                stdout += (
                    "1 M. N... 100644 100644 100644 "
                    "abc abc PAYROLL.cob\0"
                )

            return _completed_result(
                command,
                stdout=stdout,
            )

        return _completed_result(
            command,
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    status = service.unstage_paths(
        "/source/project",
        (
            "PAYROLL.cob",
        ),
    )

    assert commands[
        2
    ] == (
        "git",
        "restore",
        "--staged",
        "--",
        "PAYROLL.cob",
    )
    assert status.clean is True


def test_unstage_paths_uses_rm_cached_for_unborn_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[
        tuple[str, ...]
    ] = []
    status_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal status_reads

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
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if "status" in command:
            status_reads += 1

            stdout = (
                "# branch.oid (initial)\0"
                "# branch.head main\0"
            )

            if status_reads == 1:
                stdout += (
                    "1 A. N... 000000 100644 100644 "
                    "000 abc PAYROLL.cob\0"
                )

            return _completed_result(
                command,
                stdout=stdout,
            )

        return _completed_result(
            command,
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    status = service.unstage_paths(
        "/source/project",
        (
            "PAYROLL.cob",
        ),
    )

    assert commands[
        2
    ] == (
        "git",
        "rm",
        "--cached",
        "--ignore-unmatch",
        "--",
        "PAYROLL.cob",
    )
    assert status.head_oid is None
    assert status.clean is True


def test_unstage_all_uses_restore_staged_when_head_exists(
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
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if "status" in command:
            return _completed_result(
                command,
                stdout=(
                    "# branch.oid abc123\0"
                    "# branch.head main\0"
                ),
            )

        return _completed_result(
            command,
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    service.unstage_all(
        "/source/project",
    )

    assert commands[
        2
    ] == (
        "git",
        "restore",
        "--staged",
        "--",
        ".",
    )


def test_unstage_all_uses_rm_cached_for_unborn_repository(
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
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if "status" in command:
            return _completed_result(
                command,
                stdout=(
                    "# branch.oid (initial)\0"
                    "# branch.head main\0"
                ),
            )

        return _completed_result(
            command,
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    service.unstage_all(
        "/source/project",
    )

    assert commands[
        2
    ] == (
        "git",
        "rm",
        "--cached",
        "-r",
        "--ignore-unmatch",
        "--",
        ".",
    )


@pytest.mark.parametrize(
    "repository_paths",
    [
        (),
        [],
    ],
)
def test_stage_paths_requires_at_least_one_path(
    repository_paths: object,
) -> None:
    service = GitService()

    with pytest.raises(
        GitRepositoryPathError,
        match="At least one",
    ):
        service.stage_paths(
            "/source/project",
            repository_paths,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "repository_paths",
    [
        "PAYROLL.cob",
        Path(
            "PAYROLL.cob"
        ),
    ],
)
def test_stage_paths_rejects_single_path_as_sequence(
    repository_paths: object,
) -> None:
    service = GitService()

    with pytest.raises(
        TypeError,
        match="sequence of paths",
    ):
        service.stage_paths(
            "/source/project",
            repository_paths,  # type: ignore[arg-type]
        )


def test_stage_paths_rejects_empty_path() -> None:
    service = GitService()

    with pytest.raises(
        GitRepositoryPathError,
        match="must not be empty",
    ):
        service.stage_paths(
            "/source/project",
            (
                " ",
            ),
        )


def test_stage_paths_rejects_absolute_path() -> None:
    service = GitService()

    absolute_path = Path.cwd() / "PAYROLL.cob"

    with pytest.raises(
        GitRepositoryPathError,
        match="must be relative",
    ):
        service.stage_paths(
            "/source/project",
            (
                absolute_path,
            ),
        )


def test_stage_paths_rejects_parent_traversal() -> None:
    service = GitService()

    with pytest.raises(
        GitRepositoryPathError,
        match="must not traverse",
    ):
        service.stage_paths(
            "/source/project",
            (
                Path(
                    "src"
                )
                / ".."
                / ".."
                / "outside.cob",
            ),
        )


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

        return _completed_result(
            command,
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
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
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


def test_failed_stage_command_preserves_git_result(
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
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            return_code=128,
            stderr="unable to write index",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="unable to write index",
    ) as error:
        service.stage_paths(
            "/source/project",
            (
                "PAYROLL.cob",
            ),
        )

    assert error.value.result.return_code == 128


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

        return _completed_result(
            command,
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