"""Integration tests for the real GDB/MI adapter.

Uses a tiny, hand-compiled C program (built with a real `gcc` at test
time) rather than a GnuCOBOL binary -- these tests are about whether
the adapter correctly spawns and speaks MI to a *real* `gdb` process,
not about GnuCOBOL specifically (that's covered separately once the
compiler integration layer grows debug-build support). Skips cleanly
if `gdb` or `gcc` isn't discoverable, matching the existing GnuCOBOL
integration tests' pattern.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from opencobol2.debugger.gdb_adapter import (
    GdbAdapter,
    GdbAdapterError,
    GdbNotRunningError,
)
from opencobol2.debugger.mi_protocol import MIRecordKind


_FIXTURE_SOURCE = """\
#include <stdio.h>

int add(int a, int b) {
    int result = a + b;
    return result;
}

int main(void) {
    int x = 10;
    int y = 20;
    int sum = add(x, y);
    printf("sum=%d\\n", sum);
    return 0;
}
"""


def _require_gdb_and_gcc() -> tuple[str, str]:
    gdb_path = shutil.which(
        "gdb",
    )
    gcc_path = shutil.which(
        "gcc",
    )

    if gdb_path is None or gcc_path is None:
        pytest.skip(
            "gdb and/or gcc are not installed; skipping "
            "real GDB/MI adapter integration tests."
        )

    return gdb_path, gcc_path


def _compile_fixture(
    tmp_path: Path,
    gcc_path: str,
) -> Path:
    source_path = tmp_path / "t.c"
    source_path.write_text(
        _FIXTURE_SOURCE,
    )
    executable_path = tmp_path / "t.exe"

    result = subprocess.run(
        [
            gcc_path,
            "-g",
            "-O0",
            "-o",
            str(
                executable_path,
            ),
            str(
                source_path,
            ),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        "Fixture C program failed to compile.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    return executable_path


def test_gdb_adapter_hits_a_breakpoint_and_reads_locals(
    tmp_path: Path,
) -> None:
    gdb_path, gcc_path = (
        _require_gdb_and_gcc()
    )
    executable_path = _compile_fixture(
        tmp_path,
        gcc_path,
    )

    adapter = GdbAdapter(
        gdb_executable=gdb_path,
    )
    stopped_event = threading.Event()
    stopped_records = []

    adapter.on_stopped(
        lambda record: (
            stopped_records.append(
                record,
            ),
            stopped_event.set(),
        )
    )

    try:
        adapter.start(
            executable_path,
        )

        break_result = adapter.send_command(
            "-break-insert t.c:4",
        )
        assert (
            break_result.klass == "done"
        )
        bkpt = break_result.get(
            "bkpt",
        )
        assert bkpt["line"] == "4"

        run_result = adapter.send_command(
            "-exec-run",
        )
        assert (
            run_result.klass == "running"
        )

        assert stopped_event.wait(
            15,
        ), "Breakpoint was never hit within 15s."
        assert len(stopped_records) == 1
        assert (
            stopped_records[0].get(
                "reason",
            )
            == "breakpoint-hit"
        )

        stack_result = adapter.send_command(
            "-stack-list-frames",
        )
        stack = stack_result.get(
            "stack",
        )
        assert (
            stack[0]["frame"]["func"]
            == "add"
        )

        variables_result = adapter.send_command(
            "-stack-list-variables --all-values",
        )
        variables = {
            entry["frame"]["name"]
            if "frame" in entry
            else entry["name"]: entry
            for entry in variables_result.get(
                "variables",
            )
        }
        assert (
            variables["a"]["value"]
            == "10"
        )
        assert (
            variables["b"]["value"]
            == "20"
        )
    finally:
        adapter.terminate()


def test_gdb_adapter_raises_gdb_adapter_error_on_a_bad_command(
    tmp_path: Path,
) -> None:
    gdb_path, gcc_path = (
        _require_gdb_and_gcc()
    )
    executable_path = _compile_fixture(
        tmp_path,
        gcc_path,
    )

    adapter = GdbAdapter(
        gdb_executable=gdb_path,
    )

    try:
        adapter.start(
            executable_path,
        )

        with pytest.raises(
            GdbAdapterError,
        ):
            adapter.send_command(
                "-this-is-not-a-real-command",
            )
    finally:
        adapter.terminate()


def test_gdb_adapter_raises_when_not_started() -> None:
    adapter = GdbAdapter()

    with pytest.raises(
        GdbNotRunningError,
    ):
        adapter.send_command(
            "-exec-run",
        )


def test_gdb_adapter_terminate_stops_the_process(
    tmp_path: Path,
) -> None:
    gdb_path, gcc_path = (
        _require_gdb_and_gcc()
    )
    executable_path = _compile_fixture(
        tmp_path,
        gcc_path,
    )

    adapter = GdbAdapter(
        gdb_executable=gdb_path,
    )
    adapter.start(
        executable_path,
    )
    assert adapter.is_running is True

    adapter.terminate()

    assert adapter.is_running is False


_ENV_MARKER_FIXTURE_SOURCE = """\
#include <stdlib.h>

int main(void) {
    return 0;
}
"""


def test_gdb_adapter_start_passes_a_custom_environment_to_the_inferior(
    tmp_path: Path,
) -> None:
    gdb_path, gcc_path = (
        _require_gdb_and_gcc()
    )
    source_path = tmp_path / "env_marker.c"
    source_path.write_text(
        _ENV_MARKER_FIXTURE_SOURCE,
    )
    executable_path = (
        tmp_path / "env_marker.exe"
    )
    compile_result = subprocess.run(
        [
            gcc_path,
            "-g",
            "-O0",
            "-o",
            str(executable_path),
            str(source_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert compile_result.returncode == 0, (
        "Fixture C program failed to compile.\n"
        f"STDOUT:\n{compile_result.stdout}\n"
        f"STDERR:\n{compile_result.stderr}"
    )

    custom_environment = dict(os.environ)
    custom_environment["OPENCOBOL2_TEST_MARKER"] = (
        "opencobol2-marker-value"
    )

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
            environment=custom_environment,
        )
        adapter.send_command(
            "-break-insert main",
        )
        adapter.send_command(
            "-exec-run",
        )

        assert stopped.wait(
            15,
        ), "Breakpoint on main was never hit within 15s."

        # Ask the live inferior itself (via a real GDB inferior
        # function call) what it sees for the marker variable --
        # the most direct proof the custom environment actually
        # reached the debuggee, not just the gdb process.
        eval_result = adapter.send_command(
            '-data-evaluate-expression '
            '"(char *) getenv(\\"OPENCOBOL2_TEST_MARKER\\")"',
        )
        marker_value = eval_result.get(
            "value",
            "",
        )

        assert "opencobol2-marker-value" in marker_value, (
            "Inferior did not see the custom environment "
            f"variable. GDB reported: {marker_value!r}"
        )
    finally:
        adapter.terminate()


def test_gdb_adapter_console_output_callback_receives_messages(
    tmp_path: Path,
) -> None:
    gdb_path, gcc_path = (
        _require_gdb_and_gcc()
    )
    executable_path = _compile_fixture(
        tmp_path,
        gcc_path,
    )

    adapter = GdbAdapter(
        gdb_executable=gdb_path,
    )
    console_lines: list[str] = []
    adapter.on_console_output(
        console_lines.append,
    )

    try:
        adapter.start(
            executable_path,
        )
        adapter.send_command(
            "-break-insert main",
        )

        assert any(
            "t.exe" in line
            or "Breakpoint" in line
            for line in console_lines
        )
    finally:
        adapter.terminate()
