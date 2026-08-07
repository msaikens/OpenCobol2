"""End-to-end integration test: compile real COBOL, debug it, read a real value.

Ties together every piece built for COBOL-level debugging: compiles a
real `.cbl` program with debug symbols via the project's own GnuCOBOL
toolchain discovery, starts a real `gdb` session against it, stops at
a breakpoint set by *COBOL line number*, reads the generated C headers
to map a COBOL data name to its raw memory buffer, reads those bytes
live via GDB, and decodes them back into the value COBOL itself would
show. Skips cleanly if GnuCOBOL or gdb isn't installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from opencobol2.debugger.cobol_values import (
    DataUsage,
    decode_field_value,
    parse_picture_spec,
)
from opencobol2.debugger.gdb_adapter import GdbAdapter
from opencobol2.debugger.gnucobol_symbols import (
    parse_generated_symbol_map,
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


def test_debugger_reads_a_real_cobol_variable_end_to_end(
    tmp_path: Path,
) -> None:
    toolchain = discover_gnucobol()
    gdb_path = shutil.which(
        "gdb",
    )

    if toolchain is None or gdb_path is None:
        pytest.skip(
            "GnuCOBOL and/or gdb are not installed; skipping "
            "real COBOL debugging integration test."
        )

    source_path = tmp_path / "demo.cbl"
    source_path.write_text(
        _SOURCE,
    )
    executable_path = tmp_path / "demo.exe"

    compile_env = toolchain.process_environment(
        os.environ,
    )
    compile_result = subprocess.run(
        [
            str(
                toolchain.compiler_path,
            ),
            "-x",
            "-g",
            "-debug",
            "-o",
            str(
                executable_path,
            ),
            str(
                source_path,
            ),
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
    assert executable_path.is_file()

    local_header_path = (
        tmp_path / "demo.c.l.h"
    )
    global_header_path = (
        tmp_path / "demo.c.h"
    )
    assert (
        local_header_path.is_file()
    ), "cobc did not leave the expected generated header behind."

    symbol_map = parse_generated_symbol_map(
        local_header_path.read_text(),
        global_header_path.read_text()
        if global_header_path.is_file()
        else "",
    )
    ws_sum_symbol = symbol_map["WS-SUM"]

    adapter = GdbAdapter(
        gdb_executable=gdb_path,
    )
    stopped = threading.Event()
    adapter.on_stopped(
        lambda _record: stopped.set(),
    )

    try:
        adapter.start(
            executable_path,
            environment=compile_env,
        )

        adapter.send_command(
            "-break-insert demo.cbl:11",
        )
        adapter.send_command(
            "-exec-run",
        )
        assert stopped.wait(
            15,
        ), "Breakpoint on the DISPLAY statement was never hit."

        memory_result = adapter.send_command(
            "-data-read-memory-bytes "
            f"{ws_sum_symbol.buffer_variable} "
            f"{ws_sum_symbol.byte_length}",
        )
        raw_hex = memory_result.get(
            "memory",
        )[0]["contents"]
        raw_bytes = bytes.fromhex(
            raw_hex,
        )

        decoded_value = decode_field_value(
            raw_bytes,
            picture=parse_picture_spec(
                "PIC 9(4)",
            ),
            usage=DataUsage.DISPLAY,
        )

        assert decoded_value == "0030"
    finally:
        adapter.terminate()


_GROUP_SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. GROUPDEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 CUSTOMER-REC.
          05 CUST-AMOUNT PIC 9(4) VALUE 10.
          05 CUST-BALANCE PIC 9(4) VALUE 20.
       01 WS-REDEF-BASE PIC 9(4) VALUE 99.
       01 WS-REDEF-VIEW REDEFINES WS-REDEF-BASE PIC 9(4).
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY CUST-AMOUNT.
           DISPLAY CUST-BALANCE.
           DISPLAY WS-REDEF-VIEW.
           STOP RUN.
"""


def test_debugger_reads_a_group_nested_field_and_a_redefines_view(
    tmp_path: Path,
) -> None:
    # Editor §DebuggerLogic-1/3: a WORKING-STORAGE item nested inside a
    # group record (`CUST-AMOUNT`/`CUST-BALANCE`, both under
    # `CUSTOMER-REC`) or a REDEFINES view (`WS-REDEF-VIEW`) used to
    # have no known memory location at all, since
    # `parse_generated_symbol_map` only recognized a top-level item's
    # own dedicated buffer declaration, never the `cob_field` struct a
    # nested/redefining item gets instead.
    toolchain = discover_gnucobol()
    gdb_path = shutil.which(
        "gdb",
    )

    if toolchain is None or gdb_path is None:
        pytest.skip(
            "GnuCOBOL and/or gdb are not installed; skipping "
            "real COBOL debugging integration test."
        )

    source_path = tmp_path / "groupdemo.cbl"
    source_path.write_text(
        _GROUP_SOURCE,
    )
    executable_path = tmp_path / "groupdemo.exe"

    compile_env = toolchain.process_environment(
        os.environ,
    )
    compile_result = subprocess.run(
        [
            str(
                toolchain.compiler_path,
            ),
            "-x",
            "-g",
            "-debug",
            "-o",
            str(
                executable_path,
            ),
            str(
                source_path,
            ),
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

    local_header_path = (
        tmp_path / "groupdemo.c.l.h"
    )
    global_header_path = (
        tmp_path / "groupdemo.c.h"
    )

    symbol_map = parse_generated_symbol_map(
        local_header_path.read_text(),
        global_header_path.read_text()
        if global_header_path.is_file()
        else "",
    )

    assert "CUST-AMOUNT" in symbol_map
    assert "CUST-BALANCE" in symbol_map
    assert "WS-REDEF-VIEW" in symbol_map

    # The second group member must resolve to a real byte-offset
    # expression into the group's shared buffer, not the group's own
    # base address -- otherwise it would silently read the same bytes
    # as the first member.
    assert (
        symbol_map["CUST-AMOUNT"].buffer_variable
        != symbol_map["CUST-BALANCE"].buffer_variable
    )

    adapter = GdbAdapter(
        gdb_executable=gdb_path,
    )
    stopped = threading.Event()
    adapter.on_stopped(
        lambda _record: stopped.set(),
    )

    def read_decoded(
        symbol,
    ) -> str:
        memory_result = adapter.send_command(
            "-data-read-memory-bytes "
            f"{symbol.buffer_variable} "
            f"{symbol.byte_length}",
        )
        raw_bytes = bytes.fromhex(
            memory_result.get(
                "memory",
            )[0]["contents"],
        )

        return decode_field_value(
            raw_bytes,
            picture=parse_picture_spec(
                "PIC 9(4)",
            ),
            usage=DataUsage.DISPLAY,
        )

    try:
        adapter.start(
            executable_path,
            environment=compile_env,
        )

        adapter.send_command(
            "-break-insert groupdemo.cbl:15",
        )
        adapter.send_command(
            "-exec-run",
        )
        assert stopped.wait(
            15,
        ), "Breakpoint on STOP RUN was never hit."

        assert (
            read_decoded(
                symbol_map["CUST-AMOUNT"],
            )
            == "0010"
        )
        assert (
            read_decoded(
                symbol_map["CUST-BALANCE"],
            )
            == "0020"
        )
        assert (
            read_decoded(
                symbol_map["WS-REDEF-VIEW"],
            )
            == "0099"
        )
    finally:
        adapter.terminate()
