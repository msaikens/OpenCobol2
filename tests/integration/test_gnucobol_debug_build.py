"""Integration test for the `CompileRequest.debug_symbols` compiler flag.

Tasks #111/#117 already proved the debugger pipeline works against a
`cobc -x -g -debug` build invoked directly. What's new here: that the
*official* compiler-integration-layer path -- `CompileRequest(...,
debug_symbols=True)` through the real `GnuCobolCompiler` -- produces
the same kind of genuinely debuggable build, not just that the raw
command string looks right (see `tests/unit/test_gnucobol_command.py`
for that). Skips cleanly if GnuCOBOL or gdb isn't installed.
"""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path

import pytest

from opencobol2.compiler import (
    CompileRequest,
    CompilerExecutionStatus,
    GnuCobolCompiler,
)
from opencobol2.debugger.gdb_adapter import GdbAdapter
from opencobol2.toolchains import discover_gnucobol


_SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       PROCEDURE DIVISION.
           DISPLAY "HELLO".
           STOP RUN.
"""


def test_debug_symbols_flag_produces_a_gdb_debuggable_build(
    tmp_path: Path,
) -> None:
    toolchain = discover_gnucobol()
    gdb_path = shutil.which("gdb")

    if toolchain is None or gdb_path is None:
        pytest.skip(
            "GnuCOBOL and/or gdb are not installed; skipping "
            "real debug-symbol compile-flag integration test."
        )

    source_path = tmp_path / "demo.cbl"
    source_path.write_text(_SOURCE)
    executable_path = tmp_path / "demo.exe"

    request = CompileRequest(
        source_path=source_path,
        output_path=executable_path,
        working_directory=tmp_path,
        debug_symbols=True,
    )
    compiler = GnuCobolCompiler(toolchain=toolchain)
    compilation = compiler.compile(request)
    result = compilation.process_result

    assert result.status is CompilerExecutionStatus.COMPLETED, (
        "Real GnuCOBOL process did not complete.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert compilation.succeeded, (
        "Real GnuCOBOL debug-symbol compilation failed.\n"
        f"Command: {result.command}\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "-g" in result.command
    assert "-debug" in result.command

    local_header_path = tmp_path / "demo.c.l.h"
    assert local_header_path.is_file(), (
        "cobc did not leave the generated header the debugger needs "
        "behind -- did the -debug flag actually get passed?"
    )

    adapter = GdbAdapter(gdb_executable=gdb_path)
    stopped = threading.Event()
    adapter.on_stopped(lambda _record: stopped.set())

    try:
        adapter.start(
            executable_path,
            environment=toolchain.process_environment(os.environ),
        )
        break_result = adapter.send_command("-break-insert demo.cbl:4")
        assert break_result.get("bkpt")["line"] == "4"

        adapter.send_command("-exec-run")
        assert stopped.wait(15), "COBOL-level breakpoint was never hit."
    finally:
        adapter.terminate()


def test_debug_symbols_flag_omitted_leaves_no_generated_header(
    tmp_path: Path,
) -> None:
    toolchain = discover_gnucobol()

    if toolchain is None:
        pytest.skip(
            "GnuCOBOL is not installed; skipping real "
            "debug-symbol compile-flag integration test."
        )

    source_path = tmp_path / "demo.cbl"
    source_path.write_text(_SOURCE)
    executable_path = tmp_path / "demo.exe"

    request = CompileRequest(
        source_path=source_path,
        output_path=executable_path,
        working_directory=tmp_path,
    )
    compiler = GnuCobolCompiler(toolchain=toolchain)
    compilation = compiler.compile(request)

    assert compilation.succeeded
    assert not (tmp_path / "demo.c.l.h").exists()
