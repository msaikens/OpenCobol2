"""Reusable local compiler process execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import time

from opencobol2.compiler.models import (
    CompileRequest,
    CompileResult,
    CompilerExecutionStatus,
)


def invoke_local_compiler_process(
    *,
    request: CompileRequest,
    command: Sequence[str],
    timeout_seconds: float,
    compiler_name: str,
    working_directory: Path | str | None = None,
    environment: Mapping[str, str] | None = None,
) -> CompileResult:
    """Invoke one local compiler process and capture its result."""

    if not isinstance(
        request,
        CompileRequest,
    ):
        raise TypeError(
            "Request must be CompileRequest."
        )

    normalized_command = tuple(
        str(argument)
        for argument in command
    )

    if not normalized_command:
        raise ValueError(
            "Local compiler command must not be empty."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "Local compiler timeout must be greater than zero."
        )

    if not isinstance(
        compiler_name,
        str,
    ):
        raise TypeError(
            "Compiler name must be a string."
        )

    normalized_compiler_name = compiler_name.strip()

    if not normalized_compiler_name:
        raise ValueError(
            "Compiler name must not be empty."
        )

    normalized_working_directory = (
        request.working_directory
        if working_directory is None
        else Path(working_directory)
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
            # Editor §CompilerProcess-3: without a pinned `encoding=`,
            # decoding falls back to the system's preferred encoding
            # (`cp1252` on Windows), silently mangling non-ASCII
            # diagnostic text -- the same bug shape already found and
            # fixed for Git's own subprocess layer
            # (`git/process.py`) and for `gnucobol.py` above.
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed_seconds = (
            time.perf_counter() - started_at
        )

        return CompileResult(
            request=request,
            command=normalized_command,
            status=CompilerExecutionStatus.TIMED_OUT,
            stdout=_normalize_process_output(
                error.stdout,
            ),
            stderr=_normalize_process_output(
                error.stderr,
            ),
            elapsed_seconds=elapsed_seconds,
            error_message=(
                f"{normalized_compiler_name} compilation "
                f"timed out after {timeout_seconds:g} seconds."
            ),
        )
    except OSError as error:
        elapsed_seconds = (
            time.perf_counter() - started_at
        )

        return CompileResult(
            request=request,
            command=normalized_command,
            status=(
                CompilerExecutionStatus.FAILED_TO_START
            ),
            elapsed_seconds=elapsed_seconds,
            error_message=(
                f"Unable to start "
                f"{normalized_compiler_name}: {error}"
            ),
        )

    elapsed_seconds = (
        time.perf_counter() - started_at
    )

    return CompileResult(
        request=request,
        command=normalized_command,
        status=CompilerExecutionStatus.COMPLETED,
        return_code=completed_process.returncode,
        stdout=completed_process.stdout or "",
        stderr=completed_process.stderr or "",
        elapsed_seconds=elapsed_seconds,
    )


def collect_compiler_diagnostic_output(
    process_result: CompileResult,
) -> str:
    """Collect captured process streams for diagnostic parsing."""

    if not isinstance(
        process_result,
        CompileResult,
    ):
        raise TypeError(
            "Process result must be CompileResult."
        )

    return "\n".join(
        output
        for output in (
            process_result.stdout,
            process_result.stderr,
        )
        if output
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