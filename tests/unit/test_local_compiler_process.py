"""Unit tests for reusable local compiler process execution."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

import opencobol2.compiler.local_process as local_process
from opencobol2.compiler import (
    CompileRequest,
    CompileResult,
    CompilerExecutionStatus,
    CompilerOutputKind,
)
from opencobol2.compiler.local_process import (
    collect_compiler_diagnostic_output,
    invoke_local_compiler_process,
)


def _create_request(
    *,
    working_directory: Path | None = None,
) -> CompileRequest:
    """Create a local compilation request."""

    return CompileRequest(
        source_path=Path(
            "program.cob",
        ),
        output_path=Path(
            "program.exe",
        ),
        output_kind=CompilerOutputKind.EXECUTABLE,
        working_directory=working_directory,
    )


def test_local_process_invocation_captures_completed_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _create_request()

    captured_command = None
    captured_environment = None

    def fake_run(
        command,
        *,
        cwd,
        env,
        capture_output,
        text,
        encoding,
        errors,
        timeout,
        check,
    ):
        nonlocal captured_command
        nonlocal captured_environment

        captured_command = command
        captured_environment = env

        return subprocess.CompletedProcess(
            args=command,
            returncode=4,
            stdout="compiler output",
            stderr="compiler error",
        )

    monkeypatch.setattr(
        local_process.subprocess,
        "run",
        fake_run,
    )

    environment = {
        "PATH": "test-path",
    }

    result = invoke_local_compiler_process(
        request=request,
        command=(
            "compiler.exe",
            "program.cob",
        ),
        timeout_seconds=30,
        compiler_name="Test COBOL compiler",
        environment=environment,
    )

    assert result.status is CompilerExecutionStatus.COMPLETED
    assert result.return_code == 4
    assert result.stdout == "compiler output"
    assert result.stderr == "compiler error"
    assert captured_command == (
        "compiler.exe",
        "program.cob",
    )
    assert captured_environment == environment


def test_explicit_working_directory_overrides_request_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _create_request(
        working_directory=Path(
            "request-directory",
        ),
    )

    captured_directory = None

    def fake_run(
        command,
        *,
        cwd,
        env,
        capture_output,
        text,
        encoding,
        errors,
        timeout,
        check,
    ):
        nonlocal captured_directory
        captured_directory = cwd

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        local_process.subprocess,
        "run",
        fake_run,
    )

    invoke_local_compiler_process(
        request=request,
        command=(
            "compiler.exe",
        ),
        timeout_seconds=30,
        compiler_name="Test compiler",
        working_directory=Path(
            "configured-directory",
        ),
        environment={},
    )

    assert captured_directory == Path(
        "configured-directory",
    )


def test_request_working_directory_is_used_when_no_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_directory = Path(
        "request-directory",
    )
    request = _create_request(
        working_directory=request_directory,
    )

    captured_directory = None

    def fake_run(
        command,
        *,
        cwd,
        env,
        capture_output,
        text,
        encoding,
        errors,
        timeout,
        check,
    ):
        nonlocal captured_directory
        captured_directory = cwd

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        local_process.subprocess,
        "run",
        fake_run,
    )

    invoke_local_compiler_process(
        request=request,
        command=(
            "compiler.exe",
        ),
        timeout_seconds=30,
        compiler_name="Test compiler",
        environment={},
    )

    assert captured_directory == request_directory


def test_environment_input_is_copied_before_process_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _create_request()

    captured_environment = None

    def fake_run(
        command,
        *,
        cwd,
        env,
        capture_output,
        text,
        encoding,
        errors,
        timeout,
        check,
    ):
        nonlocal captured_environment
        captured_environment = env

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        local_process.subprocess,
        "run",
        fake_run,
    )

    environment = {
        "PATH": "test-path",
    }

    invoke_local_compiler_process(
        request=request,
        command=(
            "compiler.exe",
        ),
        timeout_seconds=30,
        compiler_name="Test compiler",
        environment=environment,
    )

    assert captured_environment == environment
    assert captured_environment is not environment


def test_timeout_becomes_timed_out_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _create_request()

    def fake_run(
        command,
        **kwargs,
    ):
        raise subprocess.TimeoutExpired(
            cmd=command,
            timeout=5,
            output=b"partial stdout",
            stderr=b"partial stderr",
        )

    monkeypatch.setattr(
        local_process.subprocess,
        "run",
        fake_run,
    )

    result = invoke_local_compiler_process(
        request=request,
        command=(
            "compiler.exe",
        ),
        timeout_seconds=5,
        compiler_name="Test compiler",
        environment={},
    )

    assert result.status is CompilerExecutionStatus.TIMED_OUT
    assert result.return_code is None
    assert result.stdout == "partial stdout"
    assert result.stderr == "partial stderr"
    assert result.error_message == (
        "Test compiler compilation timed out after 5 seconds."
    )


def test_os_error_becomes_failed_to_start_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _create_request()

    def fake_run(
        command,
        **kwargs,
    ):
        raise FileNotFoundError(
            "compiler missing",
        )

    monkeypatch.setattr(
        local_process.subprocess,
        "run",
        fake_run,
    )

    result = invoke_local_compiler_process(
        request=request,
        command=(
            "compiler.exe",
        ),
        timeout_seconds=30,
        compiler_name="Test compiler",
        environment={},
    )

    assert (
        result.status
        is CompilerExecutionStatus.FAILED_TO_START
    )
    assert result.return_code is None
    assert result.error_message == (
        "Unable to start Test compiler: compiler missing"
    )


def test_diagnostic_output_preserves_stdout_then_stderr() -> None:
    request = _create_request()

    result = CompileResult(
        request=request,
        command=(
            "compiler.exe",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=1,
        stdout="stdout diagnostic",
        stderr="stderr diagnostic",
    )

    output = collect_compiler_diagnostic_output(
        result,
    )

    assert output == (
        "stdout diagnostic\nstderr diagnostic"
    )


def test_diagnostic_output_ignores_empty_streams() -> None:
    request = _create_request()

    result = CompileResult(
        request=request,
        command=(
            "compiler.exe",
        ),
        status=CompilerExecutionStatus.COMPLETED,
        return_code=1,
        stdout="",
        stderr="stderr diagnostic",
    )

    output = collect_compiler_diagnostic_output(
        result,
    )

    assert output == "stderr diagnostic"


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0,
        -1,
    ],
)
def test_local_process_timeout_must_be_positive(
    timeout_seconds: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="timeout must be greater than zero",
    ):
        invoke_local_compiler_process(
            request=_create_request(),
            command=(
                "compiler.exe",
            ),
            timeout_seconds=timeout_seconds,
            compiler_name="Test compiler",
            environment={},
        )


def test_local_process_command_must_not_be_empty() -> None:
    with pytest.raises(
        ValueError,
        match="command must not be empty",
    ):
        invoke_local_compiler_process(
            request=_create_request(),
            command=(),
            timeout_seconds=30,
            compiler_name="Test compiler",
            environment={},
        )


def test_compiler_name_must_not_be_empty() -> None:
    with pytest.raises(
        ValueError,
        match="Compiler name must not be empty",
    ):
        invoke_local_compiler_process(
            request=_create_request(),
            command=(
                "compiler.exe",
            ),
            timeout_seconds=30,
            compiler_name="   ",
            environment={},
        )