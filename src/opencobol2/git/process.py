"""Reusable local Git process execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import time

from opencobol2.git.models import (
    GitCommandExecutionStatus,
    GitCommandResult,
)


def invoke_git_process(
    *,
    command: Sequence[str],
    timeout_seconds: float,
    working_directory: Path | str | None = None,
    environment: Mapping[str, str] | None = None,
) -> GitCommandResult:
    """Invoke one local Git process and capture its result."""

    normalized_command = tuple(
        str(
            argument,
        )
        for argument in command
    )

    if not normalized_command:
        raise ValueError(
            "Git command must not be empty."
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
            "Git process timeout must be numeric."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "Git process timeout must be greater than zero."
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
    process_environment.setdefault(
        # Without this, a git operation that needs credentials (clone,
        # fetch, pull, push) blocks waiting on an interactive terminal
        # prompt instead of failing fast -- there's no terminal to
        # prompt in this application, so let git fail immediately and
        # report the auth error instead of hanging until the timeout.
        "GIT_TERMINAL_PROMPT",
        "0",
    )

    started_at = time.perf_counter()

    try:
        completed_process = subprocess.run(
            normalized_command,
            cwd=normalized_working_directory,
            env=process_environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed_seconds = (
            time.perf_counter()
            - started_at
        )

        return GitCommandResult(
            command=normalized_command,
            status=GitCommandExecutionStatus.TIMED_OUT,
            stdout=_normalize_process_output(
                error.stdout,
            ),
            stderr=_normalize_process_output(
                error.stderr,
            ),
            elapsed_seconds=elapsed_seconds,
            error_message=(
                "Git command timed out after "
                f"{timeout_seconds:g} seconds."
            ),
        )
    except OSError as error:
        elapsed_seconds = (
            time.perf_counter()
            - started_at
        )

        return GitCommandResult(
            command=normalized_command,
            status=(
                GitCommandExecutionStatus.FAILED_TO_START
            ),
            elapsed_seconds=elapsed_seconds,
            error_message=(
                f"Unable to start Git: {error}"
            ),
        )

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    return GitCommandResult(
        command=normalized_command,
        status=GitCommandExecutionStatus.COMPLETED,
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
            "utf-8",
            errors="replace",
        )

    return output