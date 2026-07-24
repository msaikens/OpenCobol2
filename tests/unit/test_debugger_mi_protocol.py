"""Unit tests for the GDB/MI output parser.

Every fixture line below is taken verbatim from a real GDB 14.2
(MinGW-W64) session started with `--interpreter=mi2` against a
debug-symbol-enabled binary -- not hand-guessed formats.
"""

from __future__ import annotations

import pytest

from opencobol2.debugger.mi_protocol import (
    MIParseError,
    MIRecordKind,
    parse_mi_line,
)


def test_parses_empty_line_as_none() -> None:
    assert parse_mi_line("") is None


def test_parses_the_gdb_prompt() -> None:
    record = parse_mi_line(
        "(gdb) ",
    )

    assert record is not None
    assert record.kind == MIRecordKind.PROMPT
    assert record.token is None
    assert record.klass is None


def test_parses_the_gdb_prompt_without_trailing_space() -> None:
    record = parse_mi_line(
        "(gdb)",
    )

    assert record is not None
    assert record.kind == MIRecordKind.PROMPT


def test_parses_a_console_stream_record_with_escaped_newline() -> None:
    record = parse_mi_line(
        '~"Reading symbols from t.exe...\\n"',
    )

    assert record is not None
    assert record.kind == MIRecordKind.CONSOLE_STREAM
    assert record.text == "Reading symbols from t.exe...\n"


def test_parses_a_console_stream_record_with_escaped_backslashes() -> None:
    record = parse_mi_line(
        '~"C:\\\\Users\\\\Mitchell\\\\t.c\\n"',
    )

    assert record is not None
    assert (
        record.text
        == "C:\\Users\\Mitchell\\t.c\n"
    )


def test_parses_a_notify_async_record() -> None:
    record = parse_mi_line(
        '=thread-group-added,id="i1"',
    )

    assert record is not None
    assert record.kind == MIRecordKind.NOTIFY_ASYNC
    assert record.klass == "thread-group-added"
    assert record.results == {
        "id": "i1",
    }


def test_parses_a_result_record_with_no_results() -> None:
    record = parse_mi_line(
        "^running",
    )

    assert record is not None
    assert record.kind == MIRecordKind.RESULT
    assert record.klass == "running"
    assert record.results == {}


def test_parses_an_exec_async_record() -> None:
    record = parse_mi_line(
        '*running,thread-id="all"',
    )

    assert record is not None
    assert record.kind == MIRecordKind.EXEC_ASYNC
    assert record.klass == "running"
    assert record.get(
        "thread-id",
    ) == "all"


def test_parses_a_result_record_with_a_leading_token() -> None:
    record = parse_mi_line(
        '5^done,bkpt={number="2"}',
    )

    assert record is not None
    assert record.token == 5
    assert record.klass == "done"
    assert record.results == {
        "bkpt": {
            "number": "2",
        },
    }


def test_parses_an_error_result_record() -> None:
    record = parse_mi_line(
        '^error,msg="-var-create: unable to create variable object"',
    )

    assert record is not None
    assert record.klass == "error"
    assert record.get(
        "msg",
    ) == (
        "-var-create: unable to "
        "create variable object"
    )


def test_parses_a_breakpoint_insert_result_with_a_nested_tuple() -> None:
    record = parse_mi_line(
        '^done,bkpt={number="1",type="breakpoint",disp="keep",'
        'enabled="y",addr="0x00000001400016e9",func="add",'
        'file="C:/Users/Mitchell/t.c",'
        'fullname="C:\\\\Users\\\\Mitchell\\\\t.c",line="4",'
        'thread-groups=["i1"],times="0",'
        'original-location="t.c:4"}',
    )

    assert record is not None
    bkpt = record.get(
        "bkpt",
    )
    assert bkpt["number"] == "1"
    assert (
        bkpt["fullname"]
        == "C:\\Users\\Mitchell\\t.c"
    )
    assert bkpt["thread-groups"] == (
        "i1",
    )
    assert bkpt["line"] == "4"


def test_parses_a_stopped_record_with_a_list_of_anonymous_tuples() -> None:
    record = parse_mi_line(
        '*stopped,reason="breakpoint-hit",disp="keep",bkptno="1",'
        'frame={addr="0x00007ff68f4d16e9",func="add",'
        'args=[{name="a",value="10"},{name="b",value="20"}],'
        'file="t.c",line="4",arch="i386:x86-64"},'
        'thread-id="1",stopped-threads="all"',
    )

    assert record is not None
    assert record.get(
        "reason",
    ) == "breakpoint-hit"
    frame = record.get(
        "frame",
    )
    assert frame["func"] == "add"
    assert frame["args"] == (
        {
            "name": "a",
            "value": "10",
        },
        {
            "name": "b",
            "value": "20",
        },
    )


def test_parses_a_stack_list_frames_result_with_named_tuple_list_elements() -> (
    None
):
    record = parse_mi_line(
        '^done,stack=[frame={level="0",addr="0x1",func="add",'
        'file="t.c",line="4"},frame={level="1",addr="0x2",'
        'func="main",file="t.c",line="9"}]',
    )

    assert record is not None
    stack = record.get(
        "stack",
    )
    assert len(stack) == 2
    assert stack[0]["frame"]["level"] == "0"
    assert stack[1]["frame"]["func"] == "main"


def test_parses_a_stack_list_variables_result() -> None:
    record = parse_mi_line(
        '^done,variables=[{name="a",arg="1",value="10"},'
        '{name="b",arg="1",value="20"},'
        '{name="result",value="30"}]',
    )

    assert record is not None
    variables = record.get(
        "variables",
    )
    assert len(variables) == 3
    assert variables[0]["name"] == "a"
    assert variables[2]["value"] == "30"


def test_parses_an_empty_tuple_and_list() -> None:
    record = parse_mi_line(
        '^done,empty_tuple={},empty_list=[]',
    )

    assert record is not None
    assert record.get(
        "empty_tuple",
    ) == {}
    assert record.get(
        "empty_list",
    ) == ()


def test_unrecognized_line_returns_none() -> None:
    assert (
        parse_mi_line(
            "not a real mi line",
        )
        is None
    )


def test_command_echo_line_returns_none() -> None:
    # Commands the adapter *sends* (e.g. "5-break-insert main") are not
    # valid received MI records -- "-" isn't a record marker.
    assert (
        parse_mi_line(
            "5-break-insert main",
        )
        is None
    )


def test_malformed_result_raises_mi_parse_error() -> None:
    with pytest.raises(
        MIParseError,
    ):
        parse_mi_line(
            '^done,bkpt={number=',
        )


def test_unterminated_string_raises_mi_parse_error() -> None:
    with pytest.raises(
        MIParseError,
    ):
        parse_mi_line(
            '~"unterminated',
        )


def test_trailing_garbage_raises_mi_parse_error() -> None:
    with pytest.raises(
        MIParseError,
    ):
        parse_mi_line(
            '^done,a="1"trailing',
        )
