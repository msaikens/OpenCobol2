"""Unit tests for GnuCOBOL diagnostic parsing."""

from pathlib import Path

from opencobol2.compiler import (
    DiagnosticSeverity,
    parse_gnucobol_diagnostics,
)


def test_parses_gcc_style_error() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        "program.cob:42: error: syntax error, unexpected DISPLAY"
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.source_path == Path("program.cob")
    assert diagnostic.line == 42
    assert diagnostic.column is None
    assert diagnostic.message == (
        "syntax error, unexpected DISPLAY"
    )
    assert diagnostic.code is None
    assert diagnostic.has_location is True


def test_parses_gcc_style_column_and_warning_code() -> None:
    raw_text = (
        "source/program.cob:42:17: "
        "warning: value is truncated [-Wtruncate]"
    )

    diagnostics = parse_gnucobol_diagnostics(
        raw_text,
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.source_path == Path(
        "source/program.cob"
    )
    assert diagnostic.line == 42
    assert diagnostic.column == 17
    assert diagnostic.message == "value is truncated"
    assert diagnostic.code == "-Wtruncate"
    assert diagnostic.raw_text == raw_text


def test_parses_windows_drive_path_in_gcc_style() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        (
            r"C:\workspace\source\program.cob"
            ":81:9: error: invalid expression"
        )
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.source_path == Path(
        r"C:\workspace\source\program.cob"
    )
    assert diagnostic.line == 81
    assert diagnostic.column == 9
    assert diagnostic.message == "invalid expression"


def test_parses_msc_style_error() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        "program.cob(27): error: invalid statement"
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.source_path == Path("program.cob")
    assert diagnostic.line == 27
    assert diagnostic.column is None
    assert diagnostic.message == "invalid statement"


def test_parses_msc_style_column() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        (
            "source/program.cob(27,13): "
            "warning: dialect extension used [-Wdialect]"
        )
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.source_path == Path(
        "source/program.cob"
    )
    assert diagnostic.line == 27
    assert diagnostic.column == 13
    assert diagnostic.message == "dialect extension used"
    assert diagnostic.code == "-Wdialect"


def test_parses_unlocated_compiler_error() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        "cobc: error: configuration file could not be loaded"
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.source_path is None
    assert diagnostic.line is None
    assert diagnostic.column is None
    assert diagnostic.message == (
        "configuration file could not be loaded"
    )
    assert diagnostic.has_location is False


def test_fatal_error_maps_to_error_severity() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        "cobc: fatal error: compiler backend unavailable"
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.message == (
        "compiler backend unavailable"
    )


def test_ignores_source_context_and_unrelated_output() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        """\
program.cob:8: error: syntax error
       DISPLAY "HELLO"
       ^
compilation terminated
"""
    )

    assert len(diagnostics) == 1

    diagnostic = diagnostics[0]

    assert diagnostic.line == 8
    assert diagnostic.message == "syntax error"


def test_preserves_diagnostic_order() -> None:
    diagnostics = parse_gnucobol_diagnostics(
        """\
first.cob:10: warning: first problem [-Wfirst]
second.cob(20): error: second problem
note: compilation continued for diagnostics
"""
    )

    assert len(diagnostics) == 3

    assert diagnostics[0].severity is DiagnosticSeverity.WARNING
    assert diagnostics[0].message == "first problem"
    assert diagnostics[0].code == "-Wfirst"

    assert diagnostics[1].severity is DiagnosticSeverity.ERROR
    assert diagnostics[1].message == "second problem"

    assert diagnostics[2].severity is DiagnosticSeverity.NOTE
    assert diagnostics[2].message == (
        "compilation continued for diagnostics"
    )