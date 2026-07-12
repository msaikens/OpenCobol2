"""Unit tests for the Output panel widget."""

from __future__ import annotations

from opencobol2.gui.output_panel import OutputWidget


def test_output_widget_starts_empty_and_read_only(
    qapp,
) -> None:
    widget = OutputWidget()

    assert widget.toPlainText() == ""
    assert widget.isReadOnly()


def test_append_line_adds_text(
    qapp,
) -> None:
    widget = OutputWidget()

    widget.append_line("Compiling main.cbl...")
    widget.append_line("main.cbl: succeeded")

    assert (
        widget.toPlainText()
        == "Compiling main.cbl...\nmain.cbl: succeeded"
    )


def test_clear_removes_existing_text(
    qapp,
) -> None:
    widget = OutputWidget()
    widget.append_line("Some output")

    widget.clear()

    assert widget.toPlainText() == ""
