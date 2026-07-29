"""Unit tests for custom local compiler diagnostic parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from opencobol2.compiler import (
    DiagnosticSeverity,
    parse_custom_local_diagnostics,
)


def test_parse_gcc_diagnostic_with_line_and_column() -> None:
    diagnostics = parse_custom_local_diagnostics(
        "src/program.cob:12:7: error: invalid statement",
        "gcc",
    )

    assert len(
        diagnostics,
    ) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.message == "invalid statement"
    assert diagnostic.source_path == Path(
        "src/program.cob"
    )
    assert diagnostic.line == 12
    assert diagnostic.column == 7


def test_parse_gcc_warning_code() -> None:
    diagnostics = parse_custom_local_diagnostics(
        "program.cob:8: warning: possible truncation [-Wtruncate]",
        "gcc",
    )

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.message == "possible truncation"
    assert diagnostic.code == "-Wtruncate"


def test_parse_msvc_diagnostic_with_code() -> None:
    diagnostics = parse_custom_local_diagnostics(
        "program.cob(22,4): error CB1234: invalid verb",
        "msvc",
    )

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.message == "invalid verb"
    assert diagnostic.source_path == Path(
        "program.cob"
    )
    assert diagnostic.line == 22
    assert diagnostic.column == 4
    assert diagnostic.code == "CB1234"


def test_parse_unlocated_diagnostic() -> None:
    diagnostics = parse_custom_local_diagnostics(
        "compiler: fatal error: compiler configuration missing",
        "gcc",
    )

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert (
        diagnostic.message
        == "compiler configuration missing"
    )
    assert diagnostic.source_path is None
    assert diagnostic.line is None
    assert diagnostic.column is None


def test_none_diagnostic_format_returns_no_diagnostics() -> None:
    diagnostics = parse_custom_local_diagnostics(
        "program.cob:1: error: ignored",
        "none",
    )

    assert diagnostics == ()


def test_msvc_format_does_not_parse_gcc_location() -> None:
    diagnostics = parse_custom_local_diagnostics(
        "program.cob:12:7: error: invalid statement",
        "msvc",
    )

    assert diagnostics == ()


def test_gcc_format_does_not_parse_msvc_location() -> None:
    diagnostics = parse_custom_local_diagnostics(
        "program.cob(12,7): error CB1000: invalid statement",
        "gcc",
    )

    assert diagnostics == ()


def test_truncated_diagnostic_line_producing_empty_message_is_skipped() -> (
    None
):
    # Editor §CompilerProcess-2: mirrors the identical guard added to
    # `gnucobol_diagnostics.py` -- a diagnostic-shaped line truncated
    # right after its severity prefix can still match via
    # lazy-quantifier backtracking with a message that strips down to
    # empty, which would otherwise crash `CompilerDiagnostic`'s own
    # non-empty-message invariant instead of being skipped.
    diagnostics = parse_custom_local_diagnostics(
        "program.cob:5: error:  \nprogram.cob:6: error: real problem",
        "gcc",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].message == "real problem"


def test_unrecognized_severity_word_still_produces_a_diagnostic() -> None:
    # Editor §CompilerProcess-7: mirrors the identical generic fallback
    # added to `gnucobol_diagnostics.py` -- the severity word used to
    # be a closed list (`fatal error|error|warning|note`), so any other
    # category word (a hypothetical `info:` line) silently produced
    # zero diagnostics.
    diagnostics = parse_custom_local_diagnostics(
        "program.cob:9: info: additional context",
        "gcc",
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.NOTE
    assert diagnostic.source_path == Path("program.cob")
    assert diagnostic.line == 9
    assert diagnostic.message == "additional context"


def test_unknown_diagnostic_format_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported custom compiler diagnostic format",
    ):
        parse_custom_local_diagnostics(
            "error: failure",
            "custom",
        )