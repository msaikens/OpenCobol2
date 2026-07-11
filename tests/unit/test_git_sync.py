"""Unit tests for Git fetch, pull, and push operations."""

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitFetchResult,
    GitPullResult,
    GitPushResult,
    GitRepositoryStatus,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
    GitExecutableUnavailableError,
    GitPullConflictError,
    GitService,
)


def _completed_result(
    command: tuple[str, ...],
    *,
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> GitCommandResult:
    """Create one completed Git process result."""

    return GitCommandResult(
        command=command,
        status=GitCommandExecutionStatus.COMPLETED,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
    )


def _status_output() -> str:
    """Build porcelain-v2 output for a clean, tracked repository."""

    return (
        "# branch.oid abc123\0"
        "# branch.head main\0"
        "# branch.upstream origin/main\0"
        "# branch.ab +0 -0\0"
    )


# --- Model validation -------------------------------------------------


def test_pull_result_rejects_branch_without_remote() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="abc123",
        branch_name="main",
        detached=False,
        upstream="origin/main",
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="requires a remote",
    ):
        GitPullResult(
            remote=None,
            branch="main",
            repository_status=status,
        )


def test_push_result_rejects_branch_without_remote() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="abc123",
        branch_name="main",
        detached=False,
        upstream="origin/main",
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="requires a remote",
    ):
        GitPushResult(
            remote=None,
            branch="main",
            repository_status=status,
        )


# --- fetch --------------------------------------------------------------


def test_fetch_default_remote_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "fetch":
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.fetch("/source/project")

    assert result.remote is None
    assert result.repository_status.head_oid == "abc123"

    assert commands == [
        (
            "git",
            "--no-optional-locks",
            "rev-parse",
            "--show-toplevel",
        ),
        (
            "git",
            "fetch",
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


def test_fetch_specific_remote_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_fetch_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_fetch_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "fetch":
            captured_fetch_command = command
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.fetch(
        "/source/project",
        "upstream",
    )

    assert result.remote == "upstream"
    assert captured_fetch_command == (
        "git",
        "fetch",
        "--",
        "upstream",
    )


def test_fetch_rejects_blank_remote_name() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.fetch(
            "/source/project",
            "   ",
        )


def test_fetch_rejects_non_string_remote_name() -> None:
    service = GitService()

    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        service.fetch(
            "/source/project",
            42,  # type: ignore[arg-type]
        )


def test_fetch_propagates_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: could not read from remote repository",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="could not read from remote repository",
    ):
        service.fetch("/source/project")


def test_fetch_propagates_git_executable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.FAILED_TO_START,
            error_message="Unable to start Git: not found",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(GitExecutableUnavailableError):
        service.fetch("/source/project")


# --- pull -----------------------------------------------------------------


def test_pull_default_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "pull":
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.pull("/source/project")

    assert result.remote is None
    assert result.branch is None
    assert commands[1] == (
        "git",
        "pull",
    )


def test_pull_with_remote_and_branch_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_pull_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_pull_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "pull":
            captured_pull_command = command
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.pull(
        "/source/project",
        "origin",
        "main",
    )

    assert result.remote == "origin"
    assert result.branch == "main"
    assert captured_pull_command == (
        "git",
        "pull",
        "--",
        "origin",
        "main",
    )


def test_pull_rejects_branch_without_remote() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="requires an explicit remote",
    ):
        service.pull(
            "/source/project",
            branch="main",
        )


def test_pull_rejects_blank_remote_name() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.pull(
            "/source/project",
            "   ",
        )


def test_pull_rejects_blank_branch_name() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.pull(
            "/source/project",
            "origin",
            "   ",
        )


def test_pull_translates_conflict_output_to_conflict_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            return_code=1,
            stdout=(
                "Auto-merging PAYROLL.cob\n"
                "CONFLICT (content): Merge conflict in PAYROLL.cob\n"
                "Automatic merge failed; fix conflicts and then "
                "commit the result.\n"
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitPullConflictError,
        match="CONFLICT",
    ):
        service.pull("/source/project")


def test_pull_propagates_generic_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: unable to access remote",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="unable to access remote",
    ):
        service.pull("/source/project")


def test_pull_propagates_git_executable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.FAILED_TO_START,
            error_message="Unable to start Git: not found",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(GitExecutableUnavailableError):
        service.pull("/source/project")


# --- push -------------------------------------------------------------------


def test_push_default_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "push":
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.push("/source/project")

    assert result.remote is None
    assert result.branch is None
    assert commands[1] == (
        "git",
        "push",
    )


def test_push_with_remote_and_branch_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_push_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_push_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if command[1] == "push":
            captured_push_command = command
            return _completed_result(command)

        return _completed_result(
            command,
            stdout=_status_output(),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.push(
        "/source/project",
        "origin",
        "main",
    )

    assert result.remote == "origin"
    assert result.branch == "main"
    assert captured_push_command == (
        "git",
        "push",
        "--",
        "origin",
        "main",
    )


def test_push_rejects_branch_without_remote() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="requires an explicit remote",
    ):
        service.push(
            "/source/project",
            branch="main",
        )


def test_push_rejects_blank_remote_name() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.push(
            "/source/project",
            "   ",
        )


def test_push_propagates_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: authentication failed",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="authentication failed",
    ):
        service.push("/source/project")


def test_push_propagates_git_executable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        return GitCommandResult(
            command=command,
            status=GitCommandExecutionStatus.FAILED_TO_START,
            error_message="Unable to start Git: not found",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(GitExecutableUnavailableError):
        service.push("/source/project")
