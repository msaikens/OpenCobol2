"""Unit tests for Git stash management."""

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
    GitStashEntry,
    parse_git_stash_list_output,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
    GitNothingToStashError,
    GitService,
    GitStashConflictError,
    GitStashNotFoundError,
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


def _stash_output(
    entries: list[tuple[int, str, str]],
) -> str:
    """Build `git stash list` style output for given entries."""

    lines = [
        f"stash@{{{index}}}\x1f{oid}\x1f{message}"
        for index, oid, message in entries
    ]

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


def _dirty_status_output() -> str:
    """Build porcelain-v2 output for a repository with a pending change."""

    return (
        "# branch.oid abc123\0"
        "# branch.head main\0"
        "1 .M N... 100644 100644 100644 abc abc PAYROLL.cob\0"
    )


def _clean_status_output() -> str:
    """Build porcelain-v2 output for a clean repository."""

    return (
        "# branch.oid abc123\0"
        "# branch.head main\0"
    )


def _untracked_only_status_output() -> str:
    """Build porcelain-v2 output for a repository with only untracked files."""

    return (
        "# branch.oid abc123\0"
        "# branch.head main\0"
        "? new_file.cob\0"
    )


# --- parse_git_stash_list_output -------------------------------------------


def test_parse_git_stash_list_output_parses_entries() -> None:
    output = _stash_output(
        [
            (0, "abc123", "WIP on main: abc123 Fix bug"),
        ],
    )

    entries = parse_git_stash_list_output(output)

    assert entries == (
        GitStashEntry(
            index=0,
            commit_oid="abc123",
            message="WIP on main: abc123 Fix bug",
        ),
    )


def test_parse_git_stash_list_output_returns_empty_tuple_for_blank_output() -> None:
    assert parse_git_stash_list_output("") == ()


def test_parse_git_stash_list_output_rejects_invalid_selector() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid Git stash status line",
    ):
        parse_git_stash_list_output("not-a-selector\x1fabc123\x1fmessage\n")


# --- list_stashes / stash_changes ------------------------------------------


def test_list_stashes_returns_parsed_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        return _completed_result(
            command,
            stdout=_stash_output([(0, "abc123", "WIP on main")]),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    entries = service.list_stashes("/source/project")

    assert entries[0].index == 0


def test_stash_changes_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    list_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal list_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if "status" in command:
            return _completed_result(command, stdout=_dirty_status_output())

        if command[1] == "stash" and command[2] == "push":
            return _completed_result(command)

        if command[1] == "stash" and command[2] == "list":
            list_reads += 1

            if list_reads == 1:
                # Stash list read before the push: no prior stash yet.
                return _completed_result(command, stdout="")

            return _completed_result(
                command,
                stdout=_stash_output(
                    [(0, "def456", "WIP on main: abc123 Fix bug")],
                ),
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.stash_changes("/source/project")

    assert result.entry.index == 0
    assert ("git", "stash", "push") in commands


def test_stash_changes_with_include_untracked_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_push_command: tuple[str, ...] | None = None
    list_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_push_command, list_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if "status" in command:
            return _completed_result(command, stdout=_dirty_status_output())

        if command[1] == "stash" and command[2] == "push":
            captured_push_command = command
            return _completed_result(command)

        list_reads += 1

        if list_reads == 1:
            # Stash list read before the push: no prior stash yet.
            return _completed_result(command, stdout="")

        return _completed_result(
            command,
            stdout=_stash_output([(0, "def456", "Manual message")]),
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.stash_changes(
        "/source/project",
        message="Manual message",
        include_untracked=True,
    )

    assert captured_push_command == (
        "git",
        "stash",
        "push",
        "--include-untracked",
        "--message",
        "Manual message",
    )


def test_stash_changes_rejects_when_nothing_to_stash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        return _completed_result(command, stdout=_clean_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitNothingToStashError,
        match="no changes to stash",
    ):
        service.stash_changes("/source/project")


def test_stash_changes_detects_noop_when_only_untracked_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`git stash push` (no --include-untracked) is a silent no-op when the
    only dirty state is untracked files. If a prior stash already exists,
    the post-push stash list is indistinguishable from the pre-push list
    by exit code alone -- this must be detected and reported as a failure
    rather than returning the pre-existing stash as if it were new."""

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if "status" in command:
            return _completed_result(
                command,
                stdout=_untracked_only_status_output(),
            )

        if command[1] == "stash" and command[2] == "push":
            return _completed_result(command, stdout="No local changes to save\n")

        if command[1] == "stash" and command[2] == "list":
            return _completed_result(
                command,
                stdout=_stash_output(
                    [(0, "abc123", "WIP on main: prior stash")],
                ),
            )

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="did not create a new stash entry",
    ):
        service.stash_changes("/source/project")


# --- apply_stash / drop_stash -----------------------------------------------


def test_apply_stash_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if command[1] == "stash" and command[2] == "list":
            return _completed_result(
                command,
                stdout=_stash_output([(0, "abc123", "WIP")]),
            )

        if command[1] == "stash" and command[2] == "apply":
            return _completed_result(command)

        return _completed_result(command, stdout=_dirty_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.apply_stash("/source/project")

    assert result.repository_status.head_oid == "abc123"


def test_apply_stash_pop_verifies_exact_git_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_command: tuple[str, ...] | None = None

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal captured_command

        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if command[1] == "stash" and command[2] == "list":
            return _completed_result(
                command,
                stdout=_stash_output([(0, "abc123", "WIP")]),
            )

        if command[1] == "stash" and command[2] == "pop":
            captured_command = command
            return _completed_result(command)

        return _completed_result(command, stdout=_dirty_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.apply_stash("/source/project", pop=True)

    assert captured_command == (
        "git",
        "stash",
        "pop",
        "stash@{0}",
    )


def test_apply_stash_rejects_unknown_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        return _completed_result(command, stdout="")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitStashNotFoundError,
        match="does not exist",
    ):
        service.apply_stash("/source/project", index=0)


def test_apply_stash_translates_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if command[1] == "stash" and command[2] == "list":
            return _completed_result(
                command,
                stdout=_stash_output([(0, "abc123", "WIP")]),
            )

        return _completed_result(
            command,
            return_code=1,
            stdout="CONFLICT (content): Merge conflict in PAYROLL.cob\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitStashConflictError,
        match="CONFLICT",
    ):
        service.apply_stash("/source/project")


def test_drop_stash_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    list_reads = 0

    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        nonlocal list_reads

        command = kwargs["command"]
        assert isinstance(command, tuple)
        commands.append(command)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if command[1] == "stash" and command[2] == "list":
            list_reads += 1

            if list_reads == 1:
                return _completed_result(
                    command,
                    stdout=_stash_output([(0, "abc123", "WIP")]),
                )

            return _completed_result(command, stdout="")

        if command[1] == "stash" and command[2] == "drop":
            return _completed_result(command)

        raise AssertionError(f"Unexpected Git command: {command!r}")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.drop_stash("/source/project", 0)

    assert result.dropped_index == 0
    assert result.remaining == ()
    assert commands[2] == (
        "git",
        "stash",
        "drop",
        "stash@{0}",
    )


def test_drop_stash_rejects_unknown_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        return _completed_result(command, stdout="")

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitStashNotFoundError,
        match="does not exist",
    ):
        service.drop_stash("/source/project", 3)


def test_apply_stash_propagates_generic_git_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if command[1] == "stash" and command[2] == "list":
            return _completed_result(
                command,
                stdout=_stash_output([(0, "abc123", "WIP")]),
            )

        return _completed_result(
            command,
            return_code=128,
            stderr="fatal: unrelated failure",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="unrelated failure",
    ):
        service.apply_stash("/source/project")
