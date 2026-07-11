"""Unit tests for Git diff retrieval."""

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    GitCommandResult,
)
from opencobol2.services import git as git_service_module
from opencobol2.services.git import (
    GitCommandFailedError,
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


# --- get_diff ------------------------------------------------------------


def test_get_diff_worktree_verifies_exact_git_command(
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

        captured_command = command
        return _completed_result(
            command,
            stdout="diff --git a/PAYROLL.cob b/PAYROLL.cob\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    diff_text = service.get_diff("/source/project")

    assert diff_text == "diff --git a/PAYROLL.cob b/PAYROLL.cob\n"
    assert captured_command == (
        "git",
        "diff",
    )


def test_get_diff_staged_verifies_exact_git_command(
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

        captured_command = command
        return _completed_result(command)

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.get_diff("/source/project", staged=True)

    assert captured_command == (
        "git",
        "diff",
        "--cached",
    )


def test_get_diff_with_paths_verifies_exact_git_command(
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

        captured_command = command
        return _completed_result(command)

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    service.get_diff(
        "/source/project",
        staged=True,
        repository_paths=["PAYROLL.cob"],
    )

    assert captured_command == (
        "git",
        "diff",
        "--cached",
        "--",
        "PAYROLL.cob",
    )


def test_get_diff_propagates_git_command_failure(
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
        service.get_diff("/source/project")


# --- get_commit_diff ------------------------------------------------------


def test_get_commit_diff_verifies_exact_git_command(
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

        captured_command = command
        return _completed_result(
            command,
            stdout="diff --git a/PAYROLL.cob b/PAYROLL.cob\n",
        )

    monkeypatch.setattr(
        git_service_module,
        "invoke_git_process",
        invoke_git_process,
    )

    service = GitService()
    diff_text = service.get_commit_diff("/source/project", "abc123")

    assert diff_text == "diff --git a/PAYROLL.cob b/PAYROLL.cob\n"
    assert captured_command == (
        "git",
        "show",
        "--format=",
        "--patch",
        "abc123",
    )


def test_get_commit_diff_rejects_blank_commit() -> None:
    service = GitService()

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.get_commit_diff("/source/project", "   ")


def test_get_commit_diff_propagates_git_command_failure(
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
        service.get_commit_diff("/source/project", "bogus")
