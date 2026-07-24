"""Unit tests for the Threads panel widget."""

from __future__ import annotations

from opencobol2.debugger.models import StackFrame, ThreadInfo
from opencobol2.gui.threads_panel import ThreadsWidget


def test_set_threads_populates_every_column(qapp) -> None:
    widget = ThreadsWidget()

    widget.set_threads(
        (
            ThreadInfo(
                thread_id=1,
                state="stopped",
                frame=StackFrame(
                    level=0,
                    function_name="MAIN-PARA",
                    line=10,
                ),
            ),
        )
    )

    assert widget.rowCount() == 1
    assert widget.item(0, 0).text() == "1"
    assert widget.item(0, 1).text() == "stopped"
    assert widget.item(0, 2).text() == "MAIN-PARA"
    assert widget.item(0, 3).text() == "10"


def test_set_threads_handles_a_thread_with_no_frame(qapp) -> None:
    widget = ThreadsWidget()

    widget.set_threads((ThreadInfo(thread_id=2, state="running"),))

    assert widget.item(0, 2).text() == ""
    assert widget.item(0, 3).text() == ""


def test_clear_threads_empties_the_table(qapp) -> None:
    widget = ThreadsWidget()
    widget.set_threads((ThreadInfo(thread_id=1, state="stopped"),))

    widget.clear_threads()

    assert widget.rowCount() == 0
