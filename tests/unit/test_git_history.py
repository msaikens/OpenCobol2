"""Unit tests for Git commit history."""

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitCommitLogEntry,
    parse_git_log_output,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
    GitExecutableUnavailableError,
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


def _log_record(
    commit_oid: str,
    parent_oids: tuple[str, ...],
    subject: str,
    body: str = "",
) -> str:
    """Build one raw `git log` record matching `LOG_FORMAT`."""

    return "\x1f".join(
        [
            commit_oid,
            " ".join(parent_oids),
            "Mitchell Aikens",
            "mitchaikens@gmail.com",
            "2026-07-11T14:25:20-04:00",
            "Mitchell Aikens",
            "mitchaikens@gmail.com",
            "2026-07-11T14:25:20-04:00",
            subject,
            body,
        ],
    )


def _log_output(
    records: list[tuple[str, tuple[str, ...], str, str]],
) -> str:
    """Build full `git log` output matching real `LOG_FORMAT` behavior."""

    if not records:
        return ""

    return (
        "\x1e\n".join(
            _log_record(*record)
            for record in records
        )
        + "\x1e\n"
    )


# --- parse_git_log_output -------------------------------------------------


def test_parse_git_log_output_parses_single_commit() -> None:
    output = _log_output(
        [
            (
                "abc123",
                ("def456",),
                "Fix payroll rounding",
                "Body line one.\n",
            ),
        ],
    )

    entries = parse_git_log_output(output)

    assert entries == (
        GitCommitLogEntry(
            commit_oid="abc123",
            parent_oids=("def456",),
            author_name="Mitchell Aikens",
            author_email="mitchaikens@gmail.com",
            authored_at="2026-07-11T14:25:20-04:00",
            committer_name="Mitchell Aikens",
            committer_email="mitchaikens@gmail.com",
            committed_at="2026-07-11T14:25:20-04:00",
            subject="Fix payroll rounding",
            body="Body line one.\n",
        ),
    )


def test_parse_git_log_output_parses_multiple_commits_in_order() -> None:
    output = _log_output(
        [
            ("abc123", ("def456",), "Second commit", ""),
            ("def456", ("bca789",), "First follow-up", ""),
            ("bca789", (), "Initial commit", ""),
        ],
    )

    entries = parse_git_log_output(output)

    assert [entry.commit_oid for entry in entries] == [
        "abc123",
        "def456",
        "bca789",
    ]


def test_parse_git_log_output_handles_root_commit_with_no_parents() -> None:
    output = _log_output(
        [
            ("bca789", (), "Initial commit", ""),
        ],
    )

    entries = parse_git_log_output(output)

    assert entries[0].parent_oids == ()


def test_parse_git_log_output_preserves_multiline_body() -> None:
    body = (
        "Introduce feature.\n"
        "Extend service with new methods.\n"
        "Add unit tests.\n"
    )
    output = _log_output(
        [
            ("abc123", ("def456",), "Add feature", body),
        ],
    )

    entries = parse_git_log_output(output)

    assert entries[0].body == body


def test_parse_git_log_output_returns_empty_tuple_for_blank_output() -> None:
    assert parse_git_log_output("") == ()


def test_parse_git_log_output_rejects_invalid_record() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid Git log record",
    ):
        parse_git_log_output("abc123\x1fonlytwofields\x1e\n")


# --- Model validation -----------------------------------------------------


def test_commit_log_entry_requires_non_empty_commit_oid() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        GitCommitLogEntry(
            commit_oid="   ",
            parent_oids=(),
            author_name="Mitchell Aikens",
            author_email="mitchaikens@gmail.com",
            authored_at="2026-07-11T14:25:20-04:00",
            committer_name="Mitchell Aikens",
            committer_email="mitchaikens@gmail.com",
            committed_at="2026-07-11T14:25:20-04:00",
            subject="Subject",
            body="",
        )


def test_commit_log_entry_rejects_blank_parent_oid() -> None:
    with pytest.raises(
        ValueError,
        match="parent OIDs must be non-empty",
    ):
        GitCommitLogEntry(
            commit_oid="abc123",
            parent_oids=("   ",),
            author_name="Mitchell Aikens",
            author_email="mitchaikens@gmail.com",
            authored_at="2026-07-11T14:25:20-04:00",
            committer_name="Mitchell Aikens",
            committer_email="mitchaikens@gmail.com",
            committed_at="2026-07-11T14:25:20-04:00",
            subject="Subject",
            body="",
        )


# --- get_history ------------------------------------------------------------


def test_get_history_returns_parsed_entries(
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
            stdout=_log_output(
                [
                    ("abc123", ("def456",), "Fix bug", ""),
                ],
            ),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    entries = service.get_history("/source/project")

    assert len(entries) == 1
    assert entries[0].commit_oid == "abc123"


def test_get_history_returns_empty_tuple_for_unborn_head(
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

        if "status" in command:
            return _completed_result(
                command,
                stdout=(
                    "# branch.oid (initial)\0"
                    "# branch.head main\0"
                ),
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    entries = service.get_history("/source/project")

    assert entries == ()
    assert not any(
        command[1] == "log"
        for command in commands
    )


def test_get_history_with_max_count_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_log_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_log_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

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

        captured_log_command = command
        return _completed_result(
            command,
            stdout="",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.get_history(
        "/source/project",
        max_count=5,
    )

    assert captured_log_command is not None
    assert "--max-count=5" in captured_log_command


def test_get_history_with_ref_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_log_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_log_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(
                command,
                stdout="/source/project\n",
            )

        captured_log_command = command
        return _completed_result(
            command,
            stdout="",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.get_history(
        "/source/project",
        ref="release",
    )

    assert captured_log_command == (
        "git",
        "log",
        f"--format={git_service_module.LOG_FORMAT}",
        "release",
    )


def test_get_history_rejects_non_positive_max_count() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        service.get_history(
            "/source/project",
            max_count=0,
        )


def test_get_history_rejects_non_integer_max_count() -> None:
    service = GitService()

    with pytest.raises(
        TypeError,
        match="must be an integer",
    ):
        service.get_history(
            "/source/project",
            max_count="5",  # type: ignore[arg-type]
        )


def test_get_history_rejects_blank_ref() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.get_history(
            "/source/project",
            ref="   ",
        )


def test_get_history_propagates_git_command_failure(
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
            return_code=128,
            stderr="fatal: bad revision",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="bad revision",
    ):
        service.get_history("/source/project")


def test_get_history_propagates_git_executable_failure(
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
        service.get_history("/source/project")
