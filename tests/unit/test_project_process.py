"""Unit tests for local project task process execution."""

from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

from opencobol2.project import (
    TaskExecutionStatus,
    invoke_task_process,
)


def test_invoke_task_process_captures_completed_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="build output",
            stderr="",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        run,
    )

    run_id = uuid4()
    result = invoke_task_process(
        command=("cobc", "-x", "main.cob"),
        run_id=run_id,
        timeout_seconds=30,
        working_directory="/source/project",
        environment={"TEST": "1"},
    )

    assert result.status is TaskExecutionStatus.COMPLETED
    assert result.run_id == run_id
    assert result.return_code == 0
    assert result.stdout == "build output"
    assert result.succeeded is True

    assert captured["command"] == ("cobc", "-x", "main.cob")
    assert captured["cwd"] == Path("/source/project")
    assert captured["env"] == {"TEST": "1"}


def test_invoke_task_process_returns_timeout_result(
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

    result = invoke_task_process(
        command=("cobc", "-x", "main.cob"),
        run_id=uuid4(),
        timeout_seconds=5,
    )

    assert result.status is TaskExecutionStatus.TIMED_OUT
    assert result.return_code is None
    assert result.stdout == "partial"
    assert "timed out" in (result.error_message or "")


def test_invoke_task_process_returns_failed_to_start_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("cobc missing")

    monkeypatch.setattr(
        subprocess,
        "run",
        run,
    )

    result = invoke_task_process(
        command=("missing-cobc",),
        run_id=uuid4(),
        timeout_seconds=30,
    )

    assert result.status is TaskExecutionStatus.FAILED_TO_START
    assert result.return_code is None
    assert "Unable to start task process" in (
        result.error_message or ""
    )


def test_invoke_task_process_rejects_empty_command() -> None:
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        invoke_task_process(
            command=(),
            run_id=uuid4(),
            timeout_seconds=30,
        )


def test_invoke_task_process_rejects_non_uuid_run_id() -> None:
    with pytest.raises(
        TypeError,
        match="must be a UUID",
    ):
        invoke_task_process(
            command=("cobc",),
            run_id="not-a-uuid",  # type: ignore[arg-type]
            timeout_seconds=30,
        )


def test_invoke_task_process_rejects_non_positive_timeout() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        invoke_task_process(
            command=("cobc",),
            run_id=uuid4(),
            timeout_seconds=0,
        )
