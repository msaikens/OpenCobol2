"""Unit tests for the Problems panel widget."""

from __future__ import annotations

from pathlib import Path

from opencobol2.compiler import CompilerDiagnostic
from opencobol2.compiler.diagnostics import DiagnosticSeverity
from opencobol2.gui.problems_panel import ProblemsWidget


def test_problems_widget_starts_empty(
    qapp,
) -> None:
    widget = ProblemsWidget()

    assert widget.rowCount() == 0


def test_set_diagnostics_populates_rows(
    qapp,
) -> None:
    widget = ProblemsWidget()
    diagnostics = (
        CompilerDiagnostic(
            severity=DiagnosticSeverity.ERROR,
            message="unexpected end of file",
            source_path=Path("main.cbl"),
            line=5,
            column=1,
        ),
        CompilerDiagnostic(
            severity=DiagnosticSeverity.WARNING,
            message="unused data item",
        ),
    )

    widget.set_diagnostics(diagnostics)

    assert widget.rowCount() == 2
    assert widget.item(0, 0).text() == "ERROR"
    assert (
        widget.item(0, 1).text()
        == str(Path("main.cbl"))
    )
    assert widget.item(0, 2).text() == "5"
    assert widget.item(0, 3).text() == "1"
    assert (
        widget.item(0, 4).text()
        == "unexpected end of file"
    )
    assert widget.item(1, 0).text() == "WARNING"
    assert widget.item(1, 1).text() == ""
    assert widget.item(1, 2).text() == ""
    assert widget.item(1, 3).text() == ""


def test_clear_diagnostics_removes_rows(
    qapp,
) -> None:
    widget = ProblemsWidget()
    widget.set_diagnostics(
        (
            CompilerDiagnostic(
                severity=DiagnosticSeverity.NOTE,
                message="free format detected",
            ),
        )
    )

    widget.clear_diagnostics()

    assert widget.rowCount() == 0


def test_set_diagnostics_replaces_previous_rows(
    qapp,
) -> None:
    widget = ProblemsWidget()
    widget.set_diagnostics(
        (
            CompilerDiagnostic(
                severity=DiagnosticSeverity.ERROR,
                message="first",
            ),
            CompilerDiagnostic(
                severity=DiagnosticSeverity.ERROR,
                message="second",
            ),
        )
    )

    widget.set_diagnostics(
        (
            CompilerDiagnostic(
                severity=DiagnosticSeverity.WARNING,
                message="only one now",
            ),
        )
    )

    assert widget.rowCount() == 1
    assert widget.item(0, 4).text() == "only one now"
