"""Unit tests for the Call Stack panel widget."""

from __future__ import annotations

from pathlib import Path

from opencobol2.debugger.models import StackFrame
from opencobol2.gui.call_stack_panel import CallStackWidget


def test_set_frames_populates_every_column(qapp) -> None:
    widget = CallStackWidget()

    widget.set_frames(
        (
            StackFrame(
                level=0,
                function_name="MAIN-PARA",
                source_path=Path("demo.cbl"),
                line=10,
            ),
        )
    )

    assert widget.rowCount() == 1
    assert widget.item(0, 0).text() == "0"
    assert widget.item(0, 1).text() == "MAIN-PARA"
    assert widget.item(0, 2).text() == "demo.cbl"
    assert widget.item(0, 3).text() == "10"


def test_set_frames_handles_a_frame_with_no_source_info(qapp) -> None:
    widget = CallStackWidget()

    widget.set_frames(
        (
            StackFrame(level=1, function_name="ntdll!Wait"),
        )
    )

    assert widget.item(0, 2).text() == ""
    assert widget.item(0, 3).text() == ""


def test_clear_frames_empties_the_table(qapp) -> None:
    widget = CallStackWidget()
    widget.set_frames(
        (StackFrame(level=0, function_name="MAIN-PARA"),)
    )

    widget.clear_frames()

    assert widget.rowCount() == 0


def test_double_clicking_a_row_emits_frame_activated(qapp) -> None:
    widget = CallStackWidget()
    widget.set_frames(
        (
            StackFrame(
                level=0,
                function_name="MAIN-PARA",
                source_path=Path("demo.cbl"),
                line=10,
            ),
        )
    )
    received = []
    widget.frame_activated.connect(
        lambda path, line: received.append((path, line))
    )

    widget._handle_cell_double_clicked(0, 0)

    assert received == [(Path("demo.cbl"), 10)]


def test_double_clicking_a_frame_without_source_does_nothing(qapp) -> None:
    widget = CallStackWidget()
    widget.set_frames((StackFrame(level=0, function_name="ntdll!Wait"),))
    received = []
    widget.frame_activated.connect(lambda *args: received.append(args))

    widget._handle_cell_double_clicked(0, 0)

    assert received == []


def test_double_clicking_an_out_of_range_row_does_nothing(qapp) -> None:
    widget = CallStackWidget()
    received = []
    widget.frame_activated.connect(lambda *args: received.append(args))

    widget._handle_cell_double_clicked(0, 0)

    assert received == []
