"""Unit tests for local Git process execution."""

from pathlib import Path
import subprocess

import pytest

from opencobol2.git import (
    GitCommandExecutionStatus,
    invoke_git_process,
)


def test_invoke_git_process_captures_completed_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(
            kwargs,
        )

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="output",
            stderr="warning",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        run,
    )

    result = invoke_git_process(
        command=(
            "git",
            "status",
        ),
        timeout_seconds=30,
        working_directory="/source/project",
        environment={
            "TEST": "1",
        },
    )

    assert result.status is GitCommandExecutionStatus.COMPLETED
    assert result.return_code == 0
    assert result.stdout == "output"
    assert result.stderr == "warning"
    assert result.succeeded is True

    assert captured["command"] == (
        "git",
        "status",
    )
    assert captured["cwd"] == Path(
        "/source/project"
    )
    assert captured["env"] == {
        "TEST": "1",
    }
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["errors"] == "replace"
    assert captured["timeout"] == 30
    assert captured["check"] is False


def test_invoke_git_process_returns_timeout_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command,
            timeout=5,
            output="partial",
            stderr="waiting",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        run,
    )

    result = invoke_git_process(
        command=(
            "git",
            "fetch",
        ),
        timeout_seconds=5,
    )

    assert result.status is GitCommandExecutionStatus.TIMED_OUT
    assert result.return_code is None
    assert result.stdout == "partial"
    assert result.stderr == "waiting"
    assert "timed out" in (
        result.error_message
        or ""
    )


def test_invoke_git_process_returns_failed_to_start_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(
            "git missing"
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        run,
    )

    result = invoke_git_process(
        command=(
            "missing-git",
            "status",
        ),
        timeout_seconds=30,
    )

    assert (
        result.status
        is GitCommandExecutionStatus.FAILED_TO_START
    )
    assert result.return_code is None
    assert "Unable to start Git" in (
        result.error_message
        or ""
    )


def test_invoke_git_process_rejects_boolean_timeout() -> None:
    with pytest.raises(
        TypeError,
        match="must be numeric",
    ):
        invoke_git_process(
            command=(
                "git",
                "status",
            ),
            timeout_seconds=True,
        )