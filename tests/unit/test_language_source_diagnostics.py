"""Unit tests for merging lex/parse/semantic diagnostics for one document."""

from __future__ import annotations

from opencobol2.language import compute_source_diagnostics


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
