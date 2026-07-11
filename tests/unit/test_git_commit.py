"""Unit tests for staged Git commit creation."""

from pathlib import Path

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitCommitResult,
    GitRepositoryStatus,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
    GitCommitMessageError,
    GitNothingToCommitError,
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


def test_commit_result_requires_head_oid_match() -> None:
    status = GitRepositoryStatus(
        repository_root="/source/project",
        head_oid="def456",
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=0,
        behind=0,
        changes=(),
    )

    with pytest.raises(
        ValueError,
        match="must match",
    ):
        GitCommitResult(
            commit_oid="abc123",
            repository_status=status,
        )


@pytest.mark.parametrize(
    "message",
    [
        "",
        " ",
        "\t\r\n",
    ],
)
def test_commit_staged_rejects_empty_message_before_process_io(
    message: str,
) -> None:
    service = GitService()

    with pytest.raises(
        GitCommitMessageError,
        match="must not be empty",
    ):
        service.commit_staged(
            "/source/project",
            message,
        )


def test_commit_staged_rejects_non_string_message_before_process_io() -> None:
    service = GitService()

    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        service.commit_staged(
            "/source/project",
            42,  # type: ignore[arg-type]
        )


def test_commit_staged_rejects_nul_message_before_process_io() -> None:
    service = GitService()

    with pytest.raises(
        GitCommitMessageError,
        match="NUL",
    ):
        service.commit_staged(
            "/source/project",
            "Add compiler profile\0invalid",
        )


def test_commit_staged_requires_staged_changes(
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

        return _completed_result(
            command,
            stdout=(
                "# branch.oid abc123\0"
                "# branch.head main\0"
                "1 .M N... 100644 100644 100644 "
                "abc abc PAYROLL.cob\0"
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitNothingToCommitError,
        match="no staged changes",
    ):
        service.commit_staged(
            "/source/project",
            "Update payroll",
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


def test_commit_staged_commits_index_and_returns_new_head(
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

        if (
            "rev-parse" in command
            and "--show-toplevel" in command
        ):
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if "status" in command:
            status_reads += 1

            if status_reads == 1:
                return _completed_result(
                    command,
                    stdout=(
                        "# branch.oid abc123\0"
                        "# branch.head main\0"
                        "1 M. N... 100644 100644 100644 "
                        "abc def PAYROLL.cob\0"
                        "1 .M N... 100644 100644 100644 "
                        "abc def LOCAL.cob\0"
                    ),
                )

            return _completed_result(
                command,
                stdout=(
                    "# branch.oid def456\0"
                    "# branch.head main\0"
                    "1 .M N... 100644 100644 100644 "
                    "abc def LOCAL.cob\0"
                ),
            )

        if command[
            1
        ] == "commit":
            return _completed_result(
                command,
                stdout="[main def456] Update payroll\n",
            )

        if (
            "rev-parse" in command
            and command[
                -1
            ] == "HEAD"
        ):
            return _completed_result(
                command,
                stdout="def456\n",
            )

        raise AssertionError(
            f"Unexpected Git command: {command!r}"
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    result = service.commit_staged(
        "/source/project",
        "  Update payroll  ",
    )

    assert result.commit_oid == "def456"
    assert (
        result.repository_status.head_oid
        == "def456"
    )
    assert result.repository_status.clean is False
    assert (
        result.repository_status.has_staged_changes
        is False
    )
    assert (
        result.repository_status.has_unstaged_changes
        is True
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
        (
            "git",
            "commit",
            "--message",
            "Update payroll",
        ),
        (
            "git",
            "--no-optional-locks",
            "rev-parse",
            "HEAD",
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


def test_commit_staged_preserves_multiline_message_as_one_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_commit_command: tuple[str, ...] | None = None
    status_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_commit_command
        nonlocal status_reads

        command = kwargs[
            "command"
        ]
        assert isinstance(
            command,
            tuple,
        )

        if (
            "rev-parse" in command
            and "--show-toplevel" in command
        ):
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        if "status" in command:
            status_reads += 1

            if status_reads == 1:
                return _completed_result(
                    command,
                    stdout=(
                        "# branch.oid abc123\0"
                        "# branch.head main\0"
                        "1 M. N... 100644 100644 100644 "
                        "abc def PAYROLL.cob\0"
                    ),
                )

            return _completed_result(
                command,
                stdout=(
                    "# branch.oid def456\0"
                    "# branch.head main\0"
                ),
            )

        if command[
            1
        ] == "commit":
            captured_commit_command = command

            return _completed_result(
                command,
            )

        if command[
            -1
        ] == "HEAD":
            return _completed_result(
                command,
                stdout="def456\n",
            )

        raise AssertionError(
            f"Unexpected Git command: {command!r}"
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    message = (
        "Add compiler profile UI\n\n"
        "Preserve provider-specific configuration."
    )

    service.commit_staged(
        "/source/project",
        message,
    )

    assert captured_commit_command == (
        "git",
        "commit",
        "--message",
        message,
    )


def test_failed_commit_preserves_git_failure(
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
                    "1 M. N... 100644 100644 100644 "
                    "abc def PAYROLL.cob\0"
                ),
            )

        if command[
            1
        ] == "commit":
            return _completed_result(
                command,
                return_code=128,
                stderr=(
                    "Author identity unknown\n"
                    "Please tell me who you are."
                ),
            )

        raise AssertionError(
            f"Unexpected Git command: {command!r}"
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="Author identity unknown",
    ) as error:
        service.commit_staged(
            "/source/project",
            "Update payroll",
        )

    assert error.value.result.return_code == 128


def test_empty_head_oid_after_successful_commit_is_explicit_failure(
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

        if (
            "rev-parse" in command
            and "--show-toplevel" in command
        ):
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
                    "1 M. N... 100644 100644 100644 "
                    "abc def PAYROLL.cob\0"
                ),
            )

        if command[
            1
        ] == "commit":
            return _completed_result(
                command,
            )

        if command[
            -1
        ] == "HEAD":
            return _completed_result(
                command,
                stdout="\n",
            )

        raise AssertionError(
            f"Unexpected Git command: {command!r}"
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="did not return the current HEAD OID",
    ):
        service.commit_staged(
            "/source/project",
            "Update payroll",
        )


def test_commit_result_normalizes_commit_oid() -> None:
    status = GitRepositoryStatus(
        repository_root=Path(
            "/source/project"
        ),
        head_oid="abc123",
        branch_name="main",
        detached=False,
        upstream=None,
        ahead=1,
        behind=0,
        changes=(),
    )

    result = GitCommitResult(
        commit_oid=" abc123 ",
        repository_status=status,
    )

    assert result.commit_oid == "abc123"