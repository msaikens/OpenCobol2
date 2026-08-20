"""Unit tests for merging lex/parse/semantic diagnostics for one document."""

from __future__ import annotations

from opencobol2.language import (
    compute_source_diagnostics,
    tokenize_cobol_source,
)


def test_lex_diagnostic_is_surfaced() -> None:
    diagnostics = compute_source_diagnostics(
        "       DISPLAY 'UNCLOSED\n",
    )

    assert any(
        "not terminated" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_parse_diagnostic_is_surfaced() -> None:
    diagnostics = compute_source_diagnostics(
        "       DATA DIVISION.\n",
    )

    assert any(
        "Expected IDENTIFICATION DIVISION"
        in diagnostic.message
        for diagnostic in diagnostics
    )


def test_diagnostics_are_sorted_by_source_position() -> None:
    # Editor §Editor-Facing-8: diagnostics used to come back in pipeline
    # stage order (lex, then parse, then semantic) rather than source
    # order -- an early parse error and a later lex error on a
    # different line came back with the parse error listed second.
    source = (
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-X PIC X VALUE 'UNCLOSED\n"
    )

    diagnostics = compute_source_diagnostics(
        source,
    )

    assert len(diagnostics) >= 2
    positions = [
        (diagnostic.position.line, diagnostic.position.column)
        for diagnostic in diagnostics
    ]
    assert positions == sorted(
        positions,
    )
    assert any(
        "Expected IDENTIFICATION DIVISION"
        in diagnostic.message
        for diagnostic in diagnostics
    )
    assert any(
        "not terminated" in diagnostic.message
        for diagnostic in diagnostics
    )
    # The parse error (line 1) must actually come before the lex error
    # (line 3) in the returned tuple, not just happen to sort correctly.
    assert diagnostics[0].position.line == 1
    assert diagnostics[-1].position.line == 3


def test_semantic_diagnostic_is_surfaced() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TEST.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 1 TO WS-MISSING\n"
        "           STOP RUN.\n"
    )

    diagnostics = compute_source_diagnostics(
        source,
    )

    assert any(
        "Undefined data name: WS-MISSING"
        in diagnostic.message
        for diagnostic in diagnostics
    )


def test_clean_source_produces_no_diagnostics() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        '           DISPLAY "HELLO".\n'
        "           STOP RUN.\n"
    )

    assert compute_source_diagnostics(
        source,
    ) == ()


def test_malformed_source_returns_diagnostics_without_raising() -> None:
    # Garbage input is a real error, not silently ignored -- unlike
    # compute_outline/compute_fold_ranges (which have nothing to walk
    # without a valid AST), a diagnostic pass exists specifically to
    # report exactly this kind of problem back to the user.
    diagnostics = compute_source_diagnostics(
        "not a real cobol program at all {{{",
    )

    assert diagnostics != ()


def test_empty_source_reports_a_missing_identification_division() -> None:
    diagnostics = compute_source_diagnostics(
        "",
    )

    assert any(
        "Expected IDENTIFICATION DIVISION"
        in diagnostic.message
        for diagnostic in diagnostics
    )


def test_diagnostic_position_carries_line_and_column() -> None:
    diagnostics = compute_source_diagnostics(
        "       DISPLAY 'UNCLOSED\n",
    )

    assert diagnostics
    assert diagnostics[0].position.line == 1
    assert diagnostics[0].position.column > 0


def test_passing_a_precomputed_lex_result_matches_computing_it_internally() -> (
    None
):
    """`lex_result` is purely a performance shortcut for a caller (the
    syntax highlighter) that already tokenized this exact text for its
    own purposes -- passing one must produce byte-for-byte the same
    diagnostics as leaving it unset and letting this function lex the
    text itself."""

    source = (
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-X PIC X VALUE 'UNCLOSED\n"
    )

    without_precomputed = compute_source_diagnostics(
        source,
    )

    lex_result = tokenize_cobol_source(
        source,
    )
    with_precomputed = compute_source_diagnostics(
        source,
        lex_result=lex_result,
    )

    assert with_precomputed == without_precomputed
