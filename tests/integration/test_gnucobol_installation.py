"""Integration tests for a real GnuCOBOL installation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from opencobol2.compiler import (
    CobolSourceFormat,
    CompileRequest,
    CompilerExecutionStatus,
    GnuCobolCompiler,
)
from opencobol2.toolchains import (
    ToolchainSource,
    discover_gnucobol,
)


def test_discovered_gnucobol_can_compile_program(
    tmp_path: Path,
) -> None:
    """Discover a real compiler and compile COBOL through the public service."""
    toolchain = discover_gnucobol()

    if toolchain is None:
        pytest.skip(
            "GnuCOBOL is not installed or no valid cobc compiler was discovered."
        )

    assert toolchain.compiler_path.is_file()
    assert toolchain.version
    assert toolchain.version_text
    assert isinstance(toolchain.source, ToolchainSource)

    process_environment = toolchain.process_environment(
        os.environ,
    )
    path_entries = process_environment.get(
        "PATH",
        "",
    ).split(os.pathsep)

    assert path_entries
    assert Path(path_entries[0]) == toolchain.bin_directory

    source_path = tmp_path / "hello.cob"
    executable_path = tmp_path / (
        "hello.exe"
        if os.name == "nt"
        else "hello"
    )

    source_path.write_text(
        """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OPENCOBOL2-TEST.
       PROCEDURE DIVISION.
           DISPLAY "OPENCOBOL2-INTEGRATION-OK".
           STOP RUN.
""",
        encoding="utf-8",
    )

    request = CompileRequest(
        source_path=source_path,
        output_path=executable_path,
        working_directory=tmp_path,
        source_format=CobolSourceFormat.FIXED,
    )

    compiler = GnuCobolCompiler(
        toolchain=toolchain,
    )

    compilation = compiler.compile(
        request,
    )

    result = compilation.process_result

    assert result.status is CompilerExecutionStatus.COMPLETED, (
        "Real GnuCOBOL process did not complete.\n"
        f"Compiler: {toolchain.compiler_path}\n"
        f"Source: {toolchain.source}\n"
        f"Version: {toolchain.version}\n"
        f"Status: {result.status}\n"
        f"Error: {result.error_message}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert compilation.succeeded, (
        "Real GnuCOBOL compilation failed.\n"
        f"Compiler: {toolchain.compiler_path}\n"
        f"Source: {toolchain.source}\n"
        f"Version: {toolchain.version}\n"
        f"Return code: {result.return_code}\n"
        f"Diagnostics: {compilation.diagnostics!r}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert result.return_code == 0
    assert executable_path.is_file()