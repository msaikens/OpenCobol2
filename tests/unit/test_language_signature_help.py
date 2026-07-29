"""Unit tests for GnuCOBOL intrinsic FUNCTION signature help."""

from __future__ import annotations

from opencobol2.language import compute_signature_help


_SAMPLE_PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01 WS-NAME PIC X(20).\n"
    "       01 WS-RESULT PIC X(20).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE FUNCTION UPPER-CASE(WS-NAME) TO WS-RESULT\n"
    "           STOP RUN.\n"
)


def _column_of(
    source_text: str,
    line: int,
    substring: str,
) -> int:
    return (
        source_text.splitlines()[
            line - 1
        ].index(
            substring,
        )
        + 1
    )


def test_signature_help_inside_the_argument_list() -> None:
    column = (
        _column_of(
            _SAMPLE_PROGRAM,
            9,
            "WS-NAME",
        )
        + 2
    )

    info = compute_signature_help(
        _SAMPLE_PROGRAM,
        line=9,
        column=column,
    )

    assert info is not None
    assert info.name == "UPPER-CASE"
    assert "UPPER-CASE" in info.signature
    assert "argument" in info.signature


def test_signature_help_returns_none_before_the_function_name() -> None:
    column = _column_of(
        _SAMPLE_PROGRAM,
        9,
        "MOVE",
    )

    assert (
        compute_signature_help(
            _SAMPLE_PROGRAM,
            line=9,
            column=column,
        )
        is None
    )


def test_signature_help_returns_none_on_the_function_name_itself() -> None:
    column = _column_of(
        _SAMPLE_PROGRAM,
        9,
        "UPPER-CASE",
    )

    assert (
        compute_signature_help(
            _SAMPLE_PROGRAM,
            line=9,
            column=column,
        )
        is None
    )


def test_signature_help_returns_none_after_the_closing_parenthesis() -> None:
    column = _column_of(
        _SAMPLE_PROGRAM,
        9,
        "TO",
    )

    assert (
        compute_signature_help(
            _SAMPLE_PROGRAM,
            line=9,
            column=column,
        )
        is None
    )


def test_signature_help_returns_none_for_an_undocumented_function() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "           DISPLAY FUNCTION WHEN-COMPILED(WS-X).\n"
    )
    column = _column_of(
        source,
        4,
        "WS-X",
    )

    assert (
        compute_signature_help(
            source,
            line=4,
            column=column,
        )
        is None
    )


def test_signature_help_on_malformed_source_returns_none_without_raising() -> None:
    assert (
        compute_signature_help(
            "not a real cobol program {{{",
            line=1,
            column=1,
        )
        is None
    )


def test_signature_help_prefers_the_innermost_nested_function_call() -> None:
    # Editor §Editor-Facing-3: a cursor inside a nested FUNCTION call's
    # own arguments used to always resolve to the *outermost* call
    # (its parens always fully enclose the inner one's), never the
    # function the cursor is actually sitting inside of.
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-NAME PIC X(20).\n"
        "       01 WS-RESULT PIC X(20).\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE FUNCTION UPPER-CASE(FUNCTION TRIM(WS-NAME)) "
        "TO WS-RESULT.\n"
    )
    column = _column_of(
        source,
        8,
        "WS-NAME",
    )

    info = compute_signature_help(
        source,
        line=8,
        column=column,
    )

    assert info is not None
    assert info.name == "TRIM"


def test_signature_help_fires_while_the_call_is_still_unclosed() -> None:
    # Editor §Editor-Facing-6: signature help used to return nothing
    # while the user is still mid-way through typing the argument list
    # (no closing paren yet) -- exactly the moment it's most useful.
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-NAME PIC X(20).\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE FUNCTION UPPER-CASE(WS-NAME"
    )
    column = _column_of(
        source,
        7,
        "WS-NAME",
    )

    info = compute_signature_help(
        source,
        line=7,
        column=column,
    )

    assert info is not None
    assert info.name == "UPPER-CASE"


def test_signature_help_handles_nested_parentheses() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-A PIC 9(3).\n"
        "       01 WS-B PIC 9(3).\n"
        "       01 WS-RESULT PIC 9(3).\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE FUNCTION MOD((WS-A), WS-B) TO WS-RESULT.\n"
    )
    column = _column_of(
        source,
        9,
        "WS-B",
    )

    info = compute_signature_help(
        source,
        line=9,
        column=column,
    )

    assert info is not None
    assert info.name == "MOD"
