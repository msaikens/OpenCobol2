"""Unit tests for hover info over data items, paragraphs, and sections."""

from __future__ import annotations

from opencobol2.language import compute_hover


_SAMPLE_PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-PAY  PIC 9(5)V99 VALUE 0.\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE 1 TO WS-PAY\n"
    "           PERFORM OTHER-PARA\n"
    "           STOP RUN.\n"
    "       OTHER-PARA.\n"
    "           DISPLAY WS-PAY.\n"
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


def test_hover_over_a_data_item_describes_its_clauses() -> None:
    column = _column_of(
        _SAMPLE_PROGRAM,
        8,
        "WS-PAY",
    )

    info = compute_hover(
        _SAMPLE_PROGRAM,
        line=8,
        column=column,
    )

    assert info is not None
    assert info.kind == "data-item"
    assert info.name == "WS-PAY"
    assert "01" in info.detail
    assert "WS-PAY" in info.detail
    assert "PIC 9(5)V99" in info.detail
    assert "VALUE 0" in info.detail


def test_hover_over_a_paragraph_usage() -> None:
    column = _column_of(
        _SAMPLE_PROGRAM,
        9,
        "OTHER-PARA",
    )

    info = compute_hover(
        _SAMPLE_PROGRAM,
        line=9,
        column=column,
    )

    assert info is not None
    assert info.kind == "paragraph"
    assert info.name == "OTHER-PARA"
    assert "Paragraph" in info.detail
    assert "OTHER-PARA" in info.detail


def test_hover_over_a_section() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "       SETUP SECTION.\n"
        "       INIT-PARA.\n"
        "           DISPLAY 'INIT'.\n"
    )
    column = _column_of(
        source,
        4,
        "SETUP",
    )

    info = compute_hover(
        source,
        line=4,
        column=column,
    )

    assert info is not None
    assert info.kind == "section"
    assert info.name == "SETUP"
    assert "Section" in info.detail


def test_hover_returns_none_for_an_undefined_name() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "           MOVE 1 TO WS-MISSING.\n"
    )
    column = _column_of(
        source,
        4,
        "WS-MISSING",
    )

    assert (
        compute_hover(
            source,
            line=4,
            column=column,
        )
        is None
    )


def test_hover_returns_none_off_any_token() -> None:
    # Column 32 of line 1 is the period ending "IDENTIFICATION DIVISION.",
    # not an identifier or a reserved word.
    column = _column_of(
        _SAMPLE_PROGRAM,
        1,
        ".",
    )

    assert (
        compute_hover(
            _SAMPLE_PROGRAM,
            line=1,
            column=column,
        )
        is None
    )


def test_hover_over_a_documented_reserved_word_describes_it() -> None:
    column = _column_of(
        _SAMPLE_PROGRAM,
        1,
        "IDENTIFICATION",
    )

    info = compute_hover(
        _SAMPLE_PROGRAM,
        line=1,
        column=column,
    )

    assert info is not None
    assert info.kind == "keyword"
    assert info.name == "IDENTIFICATION"
    assert "IDENTIFICATION" in info.detail
    assert "division" in info.detail.lower()


def test_hover_returns_none_for_an_undocumented_reserved_word() -> None:
    # "TO" is a real reserved word (MOVE 1 TO WS-PAY), but is
    # deliberately not one of the documented ones.
    column = _column_of(
        _SAMPLE_PROGRAM,
        8,
        "TO",
    )

    assert (
        compute_hover(
            _SAMPLE_PROGRAM,
            line=8,
            column=column,
        )
        is None
    )


def test_hover_on_malformed_source_returns_none_without_raising() -> None:
    assert (
        compute_hover(
            "not a real cobol program {{{",
            line=1,
            column=1,
        )
        is None
    )
