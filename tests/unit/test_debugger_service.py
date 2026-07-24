"""Unit tests for the pure PICTURE/USAGE resolution logic in `DebuggerService`.

Real end-to-end session orchestration (spawning a real `gdb`, stopping
at a breakpoint, reading a live COBOL variable) is covered by
`tests/integration/test_debugger_service.py` instead -- this module
only covers the part of `service.py` that's plain data-transformation
over a real parsed AST, no live process involved.
"""

from __future__ import annotations

from opencobol2.debugger.cobol_values import DataUsage
from opencobol2.debugger.service import resolve_picture_and_usage
from opencobol2.language import (
    analyze_compilation_unit,
    parse_cobol_tokens,
    tokenize_cobol_source,
)


def _data_item_for(source_text: str, data_name: str):
    lex_result = tokenize_cobol_source(source_text)
    parse_result = parse_cobol_tokens(lex_result)
    analysis = analyze_compilation_unit(parse_result.unit)
    symbols = analysis.symbol_table.find_data_symbols(data_name)
    return symbols[0].item


_PROGRAM_TEMPLATE = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-ITEM  {clause_text}.\n"
    "       PROCEDURE DIVISION.\n"
    "       STOP RUN.\n"
)


def test_resolve_picture_and_usage_defaults_to_display() -> None:
    item = _data_item_for(
        _PROGRAM_TEMPLATE.format(clause_text="PIC 9(4)"),
        "WS-ITEM",
    )

    picture, usage = resolve_picture_and_usage(item)

    assert picture.is_numeric is True
    assert picture.total_digits == 4
    assert usage is DataUsage.DISPLAY


def test_resolve_picture_and_usage_reads_scale_and_sign() -> None:
    item = _data_item_for(
        _PROGRAM_TEMPLATE.format(clause_text="PIC S9(5)V99"),
        "WS-ITEM",
    )

    picture, _usage = resolve_picture_and_usage(item)

    assert picture.total_digits == 7
    assert picture.scale == 2
    assert picture.is_signed is True


def test_resolve_picture_and_usage_recognizes_explicit_usage_clause() -> None:
    item = _data_item_for(
        _PROGRAM_TEMPLATE.format(
            clause_text="PIC S9(5)V99 USAGE COMP-3",
        ),
        "WS-ITEM",
    )

    _picture, usage = resolve_picture_and_usage(item)

    assert usage is DataUsage.COMP_3


def test_resolve_picture_and_usage_recognizes_bare_usage_keyword() -> None:
    # COBOL allows USAGE keywords without the literal word "USAGE".
    item = _data_item_for(
        _PROGRAM_TEMPLATE.format(clause_text="PIC 9(4) COMP-5"),
        "WS-ITEM",
    )

    _picture, usage = resolve_picture_and_usage(item)

    assert usage is DataUsage.COMP_5


def test_resolve_picture_and_usage_recognizes_binary() -> None:
    item = _data_item_for(
        _PROGRAM_TEMPLATE.format(clause_text="PIC 9(8) BINARY"),
        "WS-ITEM",
    )

    _picture, usage = resolve_picture_and_usage(item)

    assert usage is DataUsage.BINARY


def test_resolve_picture_and_usage_alphanumeric_item() -> None:
    item = _data_item_for(
        _PROGRAM_TEMPLATE.format(clause_text="PIC X(10)"),
        "WS-ITEM",
    )

    picture, usage = resolve_picture_and_usage(item)

    assert picture.is_numeric is False
    assert usage is DataUsage.DISPLAY
