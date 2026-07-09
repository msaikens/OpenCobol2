"""Integration tests for real GnuCOBOL diagnostic output."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from opencobol2.compiler import (
    CobolSourceFormat,
    CompileRequest,
    CompilerExecutionStatus,
    DiagnosticSeverity,
    GnuCobolCompiler,
    parse_gnucobol_diagnostics,
)
from opencobol2.toolchains import discover_gnucobol


def test_real_gnucobol_error_output_can_be_parsed(
    tmp_path: Path,
) -> None:
    """Compile malformed COBOL and parse a real compiler diagnostic."""
    toolchain = discover_gnucobol()

    if toolchain is None:
        pytest.skip(
            "GnuCOBOL is not installed or no valid cobc compiler was discovered."
        )

    source_path = tmp_path / "broken.cob"
    executable_path = tmp_path / (
        "broken.exe"
        if os.name == "nt"
        else "broken"
    )

    source_path.write_text(
        """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OPENCOBOL2-BROKEN.
       PROCEDURE DIVISION.
           MOVE 1 TO
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

    result = compiler.compile(
        request,
    )

    assert result.status is CompilerExecutionStatus.COMPLETED, (
        "Real GnuCOBOL process did not complete.\n"
        f"Compiler: {toolchain.compiler_path}\n"
        f"Status: {result.status}\n"
        f"Error: {result.error_message}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    assert result.return_code is not None
    assert result.return_code != 0
    assert result.succeeded is False

    diagnostic_output = "\n".join(
        output
        for output in (
            result.stdout,
            result.stderr,
        )
        if output
    )

    diagnostics = parse_gnucobol_diagnostics(
        diagnostic_output,
    )

    assert diagnostics, (
        "Real GnuCOBOL compilation failed but no diagnostics were parsed.\n"
        f"Compiler: {toolchain.compiler_path}\n"
        f"Version: {toolchain.version}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    errors = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.severity is DiagnosticSeverity.ERROR
    )

    assert errors, (
        "Real GnuCOBOL output was parsed but produced no error diagnostics.\n"
        f"Diagnostics: {diagnostics!r}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    located_errors = tuple(
        diagnostic
        for diagnostic in errors
        if diagnostic.has_location
    )

    assert located_errors, (
        "Real GnuCOBOL errors did not include a parsed source location.\n"
        f"Diagnostics: {diagnostics!r}"
    )

    assert any(
        diagnostic.source_path is not None
        and diagnostic.source_path.name == source_path.name
        and diagnostic.line is not None
        and diagnostic.line > 0
        for diagnostic in located_errors
    ), (
        "No parsed GnuCOBOL error identified the malformed source file.\n"
        f"Expected source: {source_path}\n"
        f"Diagnostics: {diagnostics!r}"
    )