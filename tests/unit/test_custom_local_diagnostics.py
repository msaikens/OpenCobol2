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


def test_unknown_diagnostic_format_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported custom compiler diagnostic format",
    ):
        parse_custom_local_diagnostics(
            "error: failure",
            "custom",
        )