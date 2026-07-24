"""Unit tests for Qt-independent debugger domain models."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.debugger import (
    Breakpoint,
    MemoryBytes,
    RegisterValue,
    StackFrame,
    StopReason,
    ThreadInfo,
    Variable,
    WatchExpression,
)


def test_breakpoint_normalizes_source_path_to_path_object() -> None:
    breakpoint_ = Breakpoint(
        number=1,
        source_path="main.cbl",
        line=10,
    )

    assert breakpoint_.source_path == Path(
        "main.cbl",
    )
    assert breakpoint_.enabled is True
    assert breakpoint_.hit_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "number": 0,
            "source_path": "a.cbl",
            "line": 1,
        },
        {
            "number": 1,
            "source_path": "a.cbl",
            "line": 0,
        },
        {
            "number": 1,
            "source_path": "a.cbl",
            "line": 1,
            "hit_count": -1,
        },
    ],
)
def test_breakpoint_rejects_invalid_values(
    kwargs,
) -> None:
    with pytest.raises(
        ValueError,
    ):
        Breakpoint(
            **kwargs,
        )


def test_stack_frame_normalizes_source_path() -> None:
    frame = StackFrame(
        level=0,
        function_name="main",
        source_path="main.cbl",
        line=5,
    )

    assert frame.source_path == Path(
        "main.cbl",
    )


def test_stack_frame_allows_no_source_location() -> None:
    frame = StackFrame(
        level=1,
        function_name="libc_start",
    )

    assert frame.source_path is None
    assert frame.line is None


def test_stack_frame_rejects_negative_level() -> None:
    with pytest.raises(
        ValueError,
    ):
        StackFrame(
            level=-1,
            function_name="main",
        )


def test_stack_frame_rejects_non_positive_line() -> None:
    with pytest.raises(
        ValueError,
    ):
        StackFrame(
            level=0,
            function_name="main",
            line=0,
        )


def test_variable_rejects_empty_name() -> None:
    with pytest.raises(
        ValueError,
    ):
        Variable(
            name="   ",
            value="1",
        )


def test_variable_defaults() -> None:
    variable = Variable(
        name="WS-COUNT",
        value="3",
    )

    assert variable.is_argument is False
    assert variable.type_name is None


def test_thread_info_rejects_non_positive_id() -> None:
    with pytest.raises(
        ValueError,
    ):
        ThreadInfo(
            thread_id=0,
            state="running",
        )


def test_register_value_rejects_empty_name() -> None:
    with pytest.raises(
        ValueError,
    ):
        RegisterValue(
            name="",
            value="0x0",
        )


def test_memory_bytes_rejects_negative_address() -> None:
    with pytest.raises(
        ValueError,
    ):
        MemoryBytes(
            address=-1,
            data=b"",
        )


def test_memory_bytes_holds_raw_data() -> None:
    memory = MemoryBytes(
        address=0x1000,
        data=b"\x01\x02\x03",
    )

    assert memory.address == 0x1000
    assert memory.data == b"\x01\x02\x03"


def test_watch_expression_normalizes_and_requires_text() -> None:
    watch = WatchExpression(
        expression="  WS-COUNT + 1  ",
    )

    assert watch.expression == "WS-COUNT + 1"
    assert watch.value is None
    assert watch.error is None


def test_watch_expression_rejects_empty_text() -> None:
    with pytest.raises(
        ValueError,
    ):
        WatchExpression(
            expression="   ",
        )


def test_stop_reason_from_gdb_reason_maps_known_values() -> None:
    assert (
        StopReason.from_gdb_reason(
            "breakpoint-hit",
        )
        is StopReason.BREAKPOINT_HIT
    )
    assert (
        StopReason.from_gdb_reason(
            "end-stepping-range",
        )
        is StopReason.STEP_COMPLETED
    )


def test_stop_reason_from_gdb_reason_falls_back_to_other() -> None:
    assert (
        StopReason.from_gdb_reason(
            "watchpoint-trigger",
        )
        is StopReason.OTHER
    )
    assert (
        StopReason.from_gdb_reason(
            None,
        )
        is StopReason.OTHER
    )
