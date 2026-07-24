"""End-to-end integration test for `DebuggerService`.

Exercises the whole orchestration layer against a real `cobc`-compiled
COBOL program and a real `gdb` session: starting a session, setting a
breakpoint by COBOL line number, running to it, inspecting the stack/
threads/registers/memory, evaluating an arbitrary expression, reading
a decoded COBOL variable, single-stepping, and running to completion.
Skips cleanly if GnuCOBOL or gdb isn't installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from opencobol2.debugger.models import DebuggerState, StopReason
from opencobol2.debugger.service import DebuggerService
from opencobol2.language import (
    analyze_compilation_unit,
    parse_cobol_tokens,
    tokenize_cobol_source,
)
from opencobol2.toolchains import discover_gnucobol


_SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(4) VALUE 10.
       01 WS-B PIC 9(4) VALUE 20.
       01 WS-SUM PIC 9(4).
       PROCEDURE DIVISION.
       MAIN-PARA.
           ADD WS-A TO WS-B GIVING WS-SUM.
           DISPLAY "SUM=" WS-SUM.
           STOP RUN.
"""


def test_debugger_service_drives_a_full_real_session(
    tmp_path: Path,
) -> None:
    toolchain = discover_gnucobol()
    gdb_path = shutil.which("gdb")

    if toolchain is None or gdb_path is None:
        pytest.skip(
            "GnuCOBOL and/or gdb are not installed; skipping "
            "real DebuggerService integration test."
        )

    source_path = tmp_path / "demo.cbl"
    source_path.write_text(_SOURCE)
    executable_path = tmp_path / "demo.exe"

    compile_env = toolchain.process_environment(os.environ)
    compile_result = subprocess.run(
        [
            str(toolchain.compiler_path),
            "-x",
            "-g",
            "-debug",
            "-o",
            str(executable_path),
            str(source_path),
        ],
        cwd=tmp_path,
        env=compile_env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert compile_result.returncode == 0, (
        "Real GnuCOBOL compilation failed.\n"
        f"STDOUT:\n{compile_result.stdout}\n"
        f"STDERR:\n{compile_result.stderr}"
    )

    lex_result = tokenize_cobol_source(_SOURCE)
    parse_result = parse_cobol_tokens(lex_result)
    analysis = analyze_compilation_unit(parse_result.unit)

    service = DebuggerService(gdb_executable=gdb_path)
    stopped_events = []
    stopped_signal = threading.Event()
    service.on_stopped(
        lambda event: (
            stopped_events.append(event),
            stopped_signal.set(),
        ),
    )

    try:
        service.start_session(
            executable_path,
            source_path=source_path,
            symbol_table=analysis.symbol_table,
            environment=compile_env,
        )

        breakpoint_ = service.add_breakpoint("demo.cbl", 10)
        assert breakpoint_.line == 10

        service.run()
        assert stopped_signal.wait(15), "Breakpoint was never hit."
        assert stopped_events[-1].reason == StopReason.BREAKPOINT_HIT
        assert stopped_events[-1].frame is not None
        assert stopped_events[-1].frame.line == 10

        # -- stack / threads / registers / raw memory / expressions --
        frames = service.stack_frames()
        assert frames
        assert frames[0].line == 10

        threads = service.threads()
        assert threads
        assert threads[0].thread_id > 0

        registers = service.registers()
        register_names = {register.name for register in registers}
        assert "rip" in register_names

        assert service.evaluate_expression("1 + 1") == "2"

        memory = service.read_memory("&main", 4)
        assert memory.address > 0
        assert len(memory.data) == 4

        # -- the star feature: decoded COBOL variable values --
        ws_a = service.read_variable("WS-A")
        assert ws_a.value == "0010"
        ws_sum_before = service.read_variable("WS-SUM")
        assert ws_sum_before.value == "0000"

        # -- step over the ADD, confirm the decoded sum updates --
        #
        # A single -exec-next can land inside GnuCOBOL's own runtime
        # frame-management code (not yet filtered out -- "smart
        # stepping" is deferred to task #115), so step repeatedly
        # until execution actually reaches the next COBOL source line.
        for _ in range(10):
            stopped_signal.clear()
            service.step_over()
            assert stopped_signal.wait(15), "Step-over never completed."
            frame = stopped_events[-1].frame
            if (
                frame is not None
                and frame.source_path is not None
                and frame.source_path.name == "demo.cbl"
                and frame.line == 11
            ):
                break
        else:
            pytest.fail(
                "Never reached demo.cbl:11 after stepping. Last "
                f"frame: {stopped_events[-1].frame!r}",
            )

        ws_sum_after = service.read_variable("WS-SUM")
        assert ws_sum_after.value == "0030"

        # -- run to completion --
        stopped_signal.clear()
        service.continue_()
        assert stopped_signal.wait(15), "Program never ran to completion."
        assert (
            stopped_events[-1].reason == StopReason.EXITED_NORMALLY
        )
        assert service.state is DebuggerState.EXITED
    finally:
        service.stop()
