"""Unit tests for mechanical quick fixes over real diagnostics."""

from __future__ import annotations

from opencobol2.compiler import CobolSourceFormat
from opencobol2.language import compute_quick_fix, tokenize_cobol_source
from opencobol2.language.diagnostics import LexDiagnostic
from opencobol2.language.tokens import SourcePosition


_UNTERMINATED_LITERAL_SOURCE = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       PROCEDURE DIVISION.\n"
    "           DISPLAY 'unterminated literal here\n"
    "           STOP RUN.\n"
)


def _unterminated_literal_diagnostic() -> LexDiagnostic:
    result = tokenize_cobol_source(
        _UNTERMINATED_LITERAL_SOURCE,
        source_format=CobolSourceFormat.FIXED,
    )

    assert len(result.diagnostics) == 1
    return result.diagnostics[0]


def test_quick_fix_inserts_the_missing_closing_quote() -> None:
    diagnostic = _unterminated_literal_diagnostic()

    fix = compute_quick_fix(
        _UNTERMINATED_LITERAL_SOURCE,
        diagnostic,
    )

    assert fix is not None
    assert fix.insert_text == "'"
    assert fix.line == 4

    lines = _UNTERMINATED_LITERAL_SOURCE.splitlines()
    assert fix.column == len(lines[3]) + 1


def test_applying_the_quick_fix_resolves_the_diagnostic() -> None:
    diagnostic = _unterminated_literal_diagnostic()
    fix = compute_quick_fix(
        _UNTERMINATED_LITERAL_SOURCE,
        diagnostic,
    )
    assert fix is not None

    lines = _UNTERMINATED_LITERAL_SOURCE.splitlines(
        keepends=True,
    )
    target_line = lines[fix.line - 1]
    fixed_line = (
        target_line[: fix.column - 1]
        + fix.insert_text
        + target_line[fix.column - 1 :]
    )
    lines[fix.line - 1] = fixed_line
    fixed_source = "".join(
        lines,
    )

    result = tokenize_cobol_source(
        fixed_source,
        source_format=CobolSourceFormat.FIXED,
    )

    assert result.diagnostics == ()


def test_quick_fix_handles_double_quoted_literals() -> None:
    source = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO.\n"
        "       PROCEDURE DIVISION.\n"
        '           DISPLAY "unterminated\n'
        "           STOP RUN.\n"
    )
    result = tokenize_cobol_source(
        source,
        source_format=CobolSourceFormat.FIXED,
    )
    assert len(result.diagnostics) == 1

    fix = compute_quick_fix(
        source,
        result.diagnostics[0],
    )

    assert fix is not None
    assert fix.insert_text == '"'


def test_compute_quick_fix_returns_none_for_an_undocumented_diagnostic() -> None:
    diagnostic = LexDiagnostic(
        severity=(
            _unterminated_literal_diagnostic().severity
        ),
        message="Some other diagnostic message.",
        position=SourcePosition(
            line=1,
            column=1,
        ),
    )

    assert (
        compute_quick_fix(
            _UNTERMINATED_LITERAL_SOURCE,
            diagnostic,
        )
        is None
    )


def test_compute_quick_fix_returns_none_when_position_is_out_of_range() -> None:
    diagnostic = LexDiagnostic(
        severity=(
            _unterminated_literal_diagnostic().severity
        ),
        message="Alphanumeric literal is not terminated.",
        position=SourcePosition(
            line=999,
            column=1,
        ),
    )

    assert (
        compute_quick_fix(
            _UNTERMINATED_LITERAL_SOURCE,
            diagnostic,
        )
        is None
    )
