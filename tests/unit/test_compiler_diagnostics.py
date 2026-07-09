"""Unit tests for compiler diagnostic domain models."""

from pathlib import Path

import pytest

from opencobol2.compiler import (
    CompilerDiagnostic,
    DiagnosticSeverity,
)


def test_compiler_diagnostic_normalizes_values() -> None:
    diagnostic = CompilerDiagnostic(
        severity=DiagnosticSeverity.WARNING,
        message="  value is truncated  ",
        source_path="source/program.cob",
        line=42,
        column=17,
        code="  -Wtruncate  ",
        raw_text=(
            "source/program.cob:42:17: "
            "warning: value is truncated [-Wtruncate]"
        ),
    )

    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.message == "value is truncated"
    assert diagnostic.source_path == Path(
        "source/program.cob"
    )
    assert diagnostic.line == 42
    assert diagnostic.column == 17
    assert diagnostic.code == "-Wtruncate"
    assert diagnostic.raw_text == (
        "source/program.cob:42:17: "
        "warning: value is truncated [-Wtruncate]"
    )
    assert diagnostic.has_location is True


def test_empty_diagnostic_message_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="message must not be empty",
    ):
        CompilerDiagnostic(
            severity=DiagnosticSeverity.ERROR,
            message="   ",
        )


@pytest.mark.parametrize(
    "line",
    [
        0,
        -1,
    ],
)
def test_diagnostic_line_must_be_positive(
    line: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="line must be greater than zero",
    ):
        CompilerDiagnostic(
            severity=DiagnosticSeverity.ERROR,
            message="invalid syntax",
            line=line,
        )


@pytest.mark.parametrize(
    "column",
    [
        0,
        -1,
    ],
)
def test_diagnostic_column_must_be_positive(
    column: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="column must be greater than zero",
    ):
        CompilerDiagnostic(
            severity=DiagnosticSeverity.ERROR,
            message="invalid syntax",
            line=10,
            column=column,
        )


def test_diagnostic_column_requires_line() -> None:
    with pytest.raises(
        ValueError,
        match="column requires a line number",
    ):
        CompilerDiagnostic(
            severity=DiagnosticSeverity.ERROR,
            message="invalid syntax",
            column=8,
        )


def test_empty_diagnostic_code_is_normalized_to_none() -> None:
    diagnostic = CompilerDiagnostic(
        severity=DiagnosticSeverity.WARNING,
        message="dialect extension used",
        code="   ",
    )

    assert diagnostic.code is None


def test_diagnostic_without_source_line_has_no_location() -> None:
    diagnostic = CompilerDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        message="configuration file could not be loaded",
    )

    assert diagnostic.source_path is None
    assert diagnostic.line is None
    assert diagnostic.column is None
    assert diagnostic.has_location is False