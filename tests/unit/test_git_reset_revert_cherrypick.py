"""Unit tests for Git reset, revert, and cherry-pick operations."""

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCherryPickConflictError,
    GitCommandFailedError,
    GitRevertConflictError,
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
    )


# --- reset ------------------------------------------------------------------


def test_reset_mixed_default_verifies_exact_git_command(
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

        if command[1] == "reset":
            captured_command = command
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    status = service.reset("/source/project")

    assert status.head_oid == "abc123"
    assert captured_command == (
        "git",
        "reset",
        "--mixed",
        "HEAD",
        "--",
    )


def test_reset_hard_verifies_exact_git_command(
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

        if command[1] == "reset":
            captured_command = command
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.reset(
        "/source/project",
        "origin/main",
        mode="hard",
    )

    assert captured_command == (
        "git",
        "reset",
        "--hard",
        "origin/main",
        "--",
    )


def test_reset_rejects_invalid_mode() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must be 'soft', 'mixed', or 'hard'",
    ):
        service.reset(
            "/source/project",
            mode="bogus",
        )


def test_reset_rejects_dash_prefixed_target() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not start with '-'",
    ):
        service.reset(
            "/source/project",
            "--upload-pack=evil",
        )


def test_reset_propagates_git_command_failure(
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
            return_code=128,
            stderr="fatal: ambiguous argument",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="ambiguous argument",
    ):
        service.reset("/source/project", "bogus-ref")


# --- revert_commit ------------------------------------------------------


def test_revert_commit_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if command[1] == "revert":
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.revert_commit("/source/project", "abc123")

    assert result.repository_status.head_oid == "abc123"


def test_revert_commit_with_no_commit_verifies_exact_git_command(
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

        if command[1] == "revert":
            captured_command = command
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.revert_commit(
        "/source/project",
        "abc123",
        no_commit=True,
    )

    assert captured_command == (
        "git",
        "revert",
        "--no-commit",
        "abc123",
        "--",
    )


def test_revert_commit_with_mainline_verifies_exact_git_command(
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

        if command[1] == "revert":
            captured_command = command
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.revert_commit(
        "/source/project",
        "abc123",
        mainline=1,
    )

    assert captured_command == (
        "git",
        "revert",
        "-m",
        "1",
        "abc123",
        "--",
    )


def test_revert_commit_translates_conflict(
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
            return_code=1,
            stdout="error: could not revert abc123...\nCONFLICT\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitRevertConflictError,
        match="CONFLICT",
    ):
        service.revert_commit("/source/project", "abc123")


def test_revert_commit_propagates_generic_failure(
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
        service.revert_commit("/source/project", "bogus")


# --- cherry_pick_commit ------------------------------------------------


def test_cherry_pick_commit_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invoke_git_process(
        **kwargs: object,
    ) -> GitCommandResult:
        command = kwargs["command"]
        assert isinstance(command, tuple)

        if "rev-parse" in command:
            return _completed_result(command, stdout="/source/project\n")

        if command[1] == "cherry-pick":
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    result = service.cherry_pick_commit("/source/project", "abc123")

    assert result.repository_status.head_oid == "abc123"


def test_cherry_pick_commit_verifies_exact_git_command(
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

        if command[1] == "cherry-pick":
            captured_command = command
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.cherry_pick_commit(
        "/source/project",
        "abc123",
        no_commit=True,
    )

    assert captured_command == (
        "git",
        "cherry-pick",
        "--no-commit",
        "abc123",
        "--",
    )


def test_cherry_pick_commit_with_mainline_verifies_exact_git_command(
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

        if command[1] == "cherry-pick":
            captured_command = command
            return _completed_result(command)

        return _completed_result(command, stdout=_status_output())

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.cherry_pick_commit(
        "/source/project",
        "abc123",
        mainline=1,
    )

    assert captured_command == (
        "git",
        "cherry-pick",
        "-m",
        "1",
        "abc123",
        "--",
    )


def test_cherry_pick_commit_translates_conflict(
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
            return_code=1,
            stdout="error: could not apply abc123...\nCONFLICT\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCherryPickConflictError,
        match="CONFLICT",
    ):
        service.cherry_pick_commit("/source/project", "abc123")


def test_cherry_pick_commit_propagates_generic_failure(
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
            return_code=128,
            stderr="fatal: bad object",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()

    with pytest.raises(
        GitCommandFailedError,
        match="bad object",
    ):
        service.cherry_pick_commit("/source/project", "bogus")
