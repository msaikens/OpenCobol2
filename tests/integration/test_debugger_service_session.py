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
from opencobol2.debugger.service import (
    DebuggerService,
    DebuggerServiceError,
)
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
        # frame-management code rather than the next COBOL source line
        # (verified against this exact real session), so
        # step_over_cobol_line() repeats internally until it does --
        # and fires exactly one on_stopped callback for the result, not
        # one per internal step.
        stopped_events.clear()
        stopped_signal.clear()
        smart_step_event = service.step_over_cobol_line()

        assert len(stopped_events) == 1, (
            "step_over_cobol_line() must suppress intermediate "
            "internal-step callbacks and fire exactly one."
        )
        assert stopped_events[0] is smart_step_event
        assert smart_step_event.frame is not None
        assert smart_step_event.frame.source_path is not None
        assert smart_step_event.frame.source_path.name == "demo.cbl"
        assert smart_step_event.frame.line == 11

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


_CALLER_SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLERDEMO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           CALL "CALLEEDEMO".
           STOP RUN.
"""

_CALLEE_SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLEEDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CALLEE-FLAG PIC 9(1) VALUE 0.
       PROCEDURE DIVISION.
       CALLEE-PARA.
           MOVE 1 TO WS-CALLEE-FLAG.
           GOBACK.
"""


def test_step_into_cobol_line_crosses_a_real_call_boundary(
    tmp_path: Path,
) -> None:
    # Editor §DebuggerLogic-5: a single raw `-exec-step` single-steps
    # through every one of GnuCOBOL's own runtime frame-management
    # instructions in a called subprogram's prologue -- measured
    # directly at 19 raw steps just to reach the callee's own
    # `PROCEDURE DIVISION` header line, and 51-500 to reach its first
    # real statement. The previous default `max_internal_steps=50`
    # reliably failed on this exact, ordinary scenario.
    toolchain = discover_gnucobol()
    gdb_path = shutil.which("gdb")

    if toolchain is None or gdb_path is None:
        pytest.skip(
            "GnuCOBOL and/or gdb are not installed; skipping "
            "real DebuggerService integration test."
        )

    caller_path = tmp_path / "callerdemo.cbl"
    caller_path.write_text(_CALLER_SOURCE)
    callee_path = tmp_path / "calleedemo.cbl"
    callee_path.write_text(_CALLEE_SOURCE)
    executable_path = tmp_path / "callerdemo.exe"

    compile_env = toolchain.process_environment(os.environ)
    compile_result = subprocess.run(
        [
            str(toolchain.compiler_path),
            "-x",
            "-g",
            "-debug",
            "-o",
            str(executable_path),
            str(caller_path),
            str(callee_path),
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

    lex_result = tokenize_cobol_source(_CALLER_SOURCE)
    parse_result = parse_cobol_tokens(lex_result)
    analysis = analyze_compilation_unit(parse_result.unit)

    service = DebuggerService(gdb_executable=gdb_path)
    stopped_signal = threading.Event()
    service.on_stopped(lambda _event: stopped_signal.set())

    try:
        service.start_session(
            executable_path,
            source_path=caller_path,
            symbol_table=analysis.symbol_table,
            environment=compile_env,
        )

        service.add_breakpoint("callerdemo.cbl", 5)
        service.run()
        assert stopped_signal.wait(
            15,
        ), "Breakpoint on the CALL line was never hit."

        stopped_signal.clear()
        smart_step_event = service.step_into_cobol_line()

        assert smart_step_event.frame is not None
        assert smart_step_event.frame.source_path is not None
        assert (
            smart_step_event.frame.source_path.name
            == "calleedemo.cbl"
        )
    finally:
        service.stop()


def test_add_breakpoint_on_an_invalid_line_raises_debugger_service_error(
    tmp_path: Path,
) -> None:
    # Editor §DebuggerLogic-6: a raw `GdbAdapterError`/`GdbNotRunningError`/
    # `TimeoutError` from the adapter layer used to propagate straight
    # through every session method, unrelated to this class's own
    # `DebuggerServiceError` -- a caller that only catches
    # `DebuggerServiceError` around an ordinary user mistake (e.g.
    # clicking a blank/comment gutter line) would be surprised by a
    # different exception type entirely.
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
    assert compile_result.returncode == 0

    lex_result = tokenize_cobol_source(_SOURCE)
    parse_result = parse_cobol_tokens(lex_result)
    analysis = analyze_compilation_unit(parse_result.unit)

    service = DebuggerService(gdb_executable=gdb_path)

    try:
        service.start_session(
            executable_path,
            source_path=source_path,
            symbol_table=analysis.symbol_table,
            environment=compile_env,
        )

        with pytest.raises(DebuggerServiceError):
            service.add_breakpoint("demo.cbl", 9999)
    finally:
        service.stop()
