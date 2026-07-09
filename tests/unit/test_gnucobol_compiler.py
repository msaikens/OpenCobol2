"""Unit tests for GnuCOBOL compiler invocation."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

import pytest

import opencobol2.compiler.gnucobol as gnucobol
from opencobol2.compiler import (
    CompileRequest,
    CompilerExecutionStatus,
    DiagnosticSeverity,
    GnuCobolCompiler,
    build_gnucobol_command,
)
from opencobol2.toolchains import (
    GnuCobolToolchain,
    ToolchainSource,
)


def _toolchain() -> GnuCobolToolchain:
    """Create a deterministic toolchain for compiler tests."""
    return GnuCobolToolchain(
        compiler_path=(
            Path("toolchains")
            / "gnucobol"
            / "bin"
            / "cobc"
        ),
        source=ToolchainSource.EXPLICIT,
        version="3.2.0",
        version_text="cobc 3.2.0",
        info_text="build environment: test",
        environment={
            "COB_CONFIG_DIR": "toolchain/config",
        },
    )


def _request() -> CompileRequest:
    """Create a deterministic compile request."""
    return CompileRequest(
        source_path=Path("source") / "hello.cob",
        output_path=Path("build") / "hello",
        working_directory=Path("workspace"),
    )


def test_compile_returns_completed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolchain = _toolchain()
    request = _request()
    captured: dict[str, Any] = {}

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="compiler stdout",
            stderr="compiler stderr",
        )

    timestamps = iter(
        (
            10.0,
            10.25,
        )
    )

    monkeypatch.setattr(
        gnucobol.subprocess,
        "run",
        fake_run,
    )
    monkeypatch.setattr(
        gnucobol.time,
        "perf_counter",
        lambda: next(timestamps),
    )

    compiler = GnuCobolCompiler(
        toolchain=toolchain,
    )

    compilation = compiler.compile(
        request,
        base_environment={
            "PATH": "base-path",
            "CUSTOM_VALUE": "preserved",
        },
    )

    result = compilation.process_result

    assert result.status is CompilerExecutionStatus.COMPLETED
    assert result.return_code == 0
    assert result.stdout == "compiler stdout"
    assert result.stderr == "compiler stderr"
    assert result.elapsed_seconds == 0.25
    assert result.succeeded is True
    assert compilation.succeeded is True
    assert compilation.diagnostics == ()

    assert captured["command"] == build_gnucobol_command(
        toolchain,
        request,
    )

    kwargs = captured["kwargs"]

    assert kwargs["cwd"] == request.working_directory
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["errors"] == "replace"
    assert kwargs["timeout"] == 30.0
    assert kwargs["check"] is False

    environment = kwargs["env"]

    assert environment["CUSTOM_VALUE"] == "preserved"
    assert environment["COB_CONFIG_DIR"] == "toolchain/config"
    assert environment["PATH"] == os.pathsep.join(
        (
            str(toolchain.bin_directory),
            "base-path",
        )
    )


def test_nonzero_return_code_is_completed_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolchain = _toolchain()
    request = _request()

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="syntax error",
        )

    monkeypatch.setattr(
        gnucobol.subprocess,
        "run",
        fake_run,
    )

    compiler = GnuCobolCompiler(
        toolchain=toolchain,
    )

    compilation = compiler.compile(
        request,
        base_environment={},
    )

    result = compilation.process_result

    assert result.status is CompilerExecutionStatus.COMPLETED
    assert result.return_code == 1
    assert result.stderr == "syntax error"
    assert result.succeeded is False
    assert compilation.succeeded is False


def test_compile_parses_captured_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolchain = _toolchain()
    request = _request()

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout=(
                "program.cob:5: warning: "
                "dialect extension used [-Wdialect]"
            ),
            stderr=(
                "program.cob:6: error: "
                "invalid statement"
            ),
        )

    monkeypatch.setattr(
        gnucobol.subprocess,
        "run",
        fake_run,
    )

    compiler = GnuCobolCompiler(
        toolchain=toolchain,
    )

    compilation = compiler.compile(
        request,
        base_environment={},
    )

    assert len(compilation.diagnostics) == 2

    warning = compilation.diagnostics[0]

    assert warning.severity is DiagnosticSeverity.WARNING
    assert warning.line == 5
    assert warning.message == "dialect extension used"
    assert warning.code == "-Wdialect"

    error = compilation.diagnostics[1]

    assert error.severity is DiagnosticSeverity.ERROR
    assert error.line == 6
    assert error.message == "invalid statement"


def test_failed_process_start_returns_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolchain = _toolchain()
    request = _request()

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(
            2,
            "No such file or directory",
        )

    timestamps = iter(
        (
            20.0,
            20.1,
        )
    )

    monkeypatch.setattr(
        gnucobol.subprocess,
        "run",
        fake_run,
    )
    monkeypatch.setattr(
        gnucobol.time,
        "perf_counter",
        lambda: next(timestamps),
    )

    compiler = GnuCobolCompiler(
        toolchain=toolchain,
    )

    compilation = compiler.compile(
        request,
        base_environment={},
    )

    result = compilation.process_result

    assert (
        result.status
        is CompilerExecutionStatus.FAILED_TO_START
    )
    assert result.return_code is None
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.elapsed_seconds == pytest.approx(0.1)
    assert "Unable to start GnuCOBOL compiler" in (
        result.error_message or ""
    )
    assert "No such file or directory" in (
        result.error_message or ""
    )
    assert result.succeeded is False
    assert compilation.succeeded is False
    assert compilation.diagnostics == ()


def test_timeout_returns_partial_captured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolchain = _toolchain()
    request = _request()

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            cmd=command,
            timeout=5.0,
            output=b"partial stdout\xff",
            stderr=b"partial stderr\xff",
        )

    timestamps = iter(
        (
            30.0,
            35.0,
        )
    )

    monkeypatch.setattr(
        gnucobol.subprocess,
        "run",
        fake_run,
    )
    monkeypatch.setattr(
        gnucobol.time,
        "perf_counter",
        lambda: next(timestamps),
    )

    compiler = GnuCobolCompiler(
        toolchain=toolchain,
        timeout_seconds=5.0,
    )

    compilation = compiler.compile(
        request,
        base_environment={},
    )

    result = compilation.process_result

    assert result.status is CompilerExecutionStatus.TIMED_OUT
    assert result.return_code is None
    assert result.stdout == "partial stdout\ufffd"
    assert result.stderr == "partial stderr\ufffd"
    assert result.elapsed_seconds == 5.0
    assert result.error_message == (
        "GnuCOBOL compilation timed out after 5 seconds."
    )
    assert result.succeeded is False
    assert compilation.succeeded is False


def test_custom_timeout_is_passed_to_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolchain = _toolchain()
    request = _request()
    captured_timeout: list[float] = []

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured_timeout.append(
            kwargs["timeout"]
        )

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        gnucobol.subprocess,
        "run",
        fake_run,
    )

    compiler = GnuCobolCompiler(
        toolchain=toolchain,
        timeout_seconds=12.5,
    )

    compiler.compile(
        request,
        base_environment={},
    )

    assert captured_timeout == [
        12.5,
    ]


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0.0,
        -1.0,
    ],
)
def test_compiler_timeout_must_be_positive(
    timeout_seconds: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        GnuCobolCompiler(
            toolchain=_toolchain(),
            timeout_seconds=timeout_seconds,
        )