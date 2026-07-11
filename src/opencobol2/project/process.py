"""Reusable local process execution for project tasks and launches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import time
from uuid import UUID

from opencobol2.project.models import (
    TaskExecutionStatus,
    TaskRunResult,
)


def invoke_task_process(
    *,
    command: Sequence[str],
    run_id: UUID,
    timeout_seconds: float,
    working_directory: Path | str | None = None,
    environment: Mapping[str, str] | None = None,
) -> TaskRunResult:
    """Invoke one local task or launch process and capture its result."""

    normalized_command = tuple(
        str(
            argument,
        )
        for argument in command
    )

    if not normalized_command:
        raise ValueError(
            "Task run command must not be empty."
        )

    if not isinstance(
        run_id,
        UUID,
    ):
        raise TypeError(
            "Task run ID must be a UUID."
        )

    if (
        not isinstance(
            timeout_seconds,
            (
                int,
                float,
            ),
        )
        or isinstance(
            timeout_seconds,
            bool,
        )
    ):
        raise TypeError(
            "Task run timeout must be numeric."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "Task run timeout must be greater than zero."
        )

    normalized_working_directory = (
        None
        if working_directory is None
        else Path(
            working_directory,
        )
    )

    process_environment = dict(
        os.environ
        if environment is None
        else environment
    )

    started_at = time.perf_counter()

    try:
        completed_process = subprocess.run(
            normalized_command,
            cwd=normalized_working_directory,
            env=process_environment,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed_seconds = (
            time.perf_counter()
            - started_at
        )

        return TaskRunResult(
            run_id=run_id,
            command=normalized_command,
            status=TaskExecutionStatus.TIMED_OUT,
            stdout=_normalize_process_output(
                error.stdout,
            ),
            stderr=_normalize_process_output(
                error.stderr,
            ),
            elapsed_seconds=elapsed_seconds,
            error_message=(
                "Task run timed out after "
                f"{timeout_seconds:g} seconds."
            ),
        )
    except OSError as error:
        elapsed_seconds = (
            time.perf_counter()
            - started_at
        )

        return TaskRunResult(
            run_id=run_id,
            command=normalized_command,
            status=(
                TaskExecutionStatus.FAILED_TO_START
            ),
            elapsed_seconds=elapsed_seconds,
            error_message=(
                f"Unable to start task process: {error}"
            ),
        )

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    return TaskRunResult(
        run_id=run_id,
        command=normalized_command,
        status=TaskExecutionStatus.COMPLETED,
        return_code=completed_process.returncode,
        stdout=completed_process.stdout or "",
        stderr=completed_process.stderr or "",
        elapsed_seconds=elapsed_seconds,
    )


def _normalize_process_output(
    output: bytes | str | None,
) -> str:
    """Normalize captured subprocess output to text."""

    if output is None:
        return ""

    if isinstance(
        output,
        bytes,
    ):
        return output.decode(
            errors="replace",
        )

    return output
