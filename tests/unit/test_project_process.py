"""Unit tests for local project task process execution."""

import os
from pathlib import Path
import subprocess
import sys
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


# --- Real subprocess execution (no subprocess.run mocking) -----------------
#
# Every test above mocks subprocess.run, so none of them exercise the
# real interaction between this module and the OS process/pipe layer.
# These use the real Python interpreter as a stand-in child process.


def test_invoke_task_process_runs_a_real_process(
    tmp_path: Path,
) -> None:
    result = invoke_task_process(
        command=(
            sys.executable,
            "-c",
            "print('hello from child')",
        ),
        run_id=uuid4(),
        timeout_seconds=30,
        working_directory=tmp_path,
    )

    assert result.status is TaskExecutionStatus.COMPLETED
    assert result.return_code == 0
    assert "hello from child" in result.stdout


def test_invoke_task_process_passes_working_directory_and_environment(
    tmp_path: Path,
) -> None:
    child_environment = dict(os.environ)
    child_environment["OC2_TEST_VAR"] = "expected-value"

    result = invoke_task_process(
        command=(
            sys.executable,
            "-c",
            "import os; print(os.getcwd()); print(os.environ['OC2_TEST_VAR'])",
        ),
        run_id=uuid4(),
        timeout_seconds=30,
        working_directory=tmp_path,
        environment=child_environment,
    )

    assert result.status is TaskExecutionStatus.COMPLETED
    output_lines = result.stdout.splitlines()
    assert Path(output_lines[0]) == tmp_path.resolve()
    assert output_lines[1] == "expected-value"


def test_invoke_task_process_real_timeout_kills_a_slow_process() -> None:
    result = invoke_task_process(
        command=(
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ),
        run_id=uuid4(),
        timeout_seconds=0.5,
    )

    assert result.status is TaskExecutionStatus.TIMED_OUT


def test_invoke_task_process_real_failed_to_start() -> None:
    result = invoke_task_process(
        command=("definitely-not-a-real-executable-xyz",),
        run_id=uuid4(),
        timeout_seconds=5,
    )

    assert result.status is TaskExecutionStatus.FAILED_TO_START
