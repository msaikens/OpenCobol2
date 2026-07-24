"""Unit tests for `DebugSessionController`'s pure bridging/bookkeeping logic.

Uses a lightweight stand-in for `DebuggerService` rather than a real GDB
session -- the controller only forwards calls and tracks which source
lines are already synced as real breakpoints, none of which needs a
live process to verify. Real end-to-end session behavior is covered by
`tests/integration/test_debugger_service_session.py`.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from opencobol2.debugger.models import Breakpoint
from opencobol2.gui.debug_session import (
    DebugSessionController,
    DebugSessionError,
)


class _FakeDebuggerService:
    """Records calls in place of a real `DebuggerService`."""

    def __init__(self) -> None:
        self.stopped_callback = None
        self.run_called = False
        self.stop_called = False
        self.continue_called = False
        self.added_breakpoints: list[tuple[str, int]] = []
        self.removed_breakpoint_numbers: list[int] = []
        self._next_breakpoint_number = 1

    def on_stopped(self, callback) -> None:
        self.stopped_callback = callback

    def run(self) -> None:
        self.run_called = True

    def stop(self) -> None:
        self.stop_called = True

    def continue_(self) -> None:
        self.continue_called = True

    def add_breakpoint(self, source_file: str, line: int) -> Breakpoint:
        self.added_breakpoints.append((source_file, line))
        number = self._next_breakpoint_number
        self._next_breakpoint_number += 1

        return Breakpoint(
            number=number,
            source_path=Path(source_file),
            line=line,
        )

    def remove_breakpoint(self, number: int) -> None:
        self.removed_breakpoint_numbers.append(number)

    def breakpoints(self) -> tuple[Breakpoint, ...]:
        return ()


def test_start_seeds_breakpoints_and_runs(qapp) -> None:
    controller = DebugSessionController()
    service = _FakeDebuggerService()
    document_id = uuid4()

    controller.start(
        service,
        source_path=Path("demo.cbl"),
        document_id=document_id,
        breakpoint_lines=(10, 11),
    )

    assert controller.is_active is True
    assert controller.source_path == Path("demo.cbl")
    assert controller.document_id == document_id
    assert service.added_breakpoints == [
        ("demo.cbl", 10),
        ("demo.cbl", 11),
    ]
    assert service.run_called is True


def test_start_twice_raises(qapp) -> None:
    controller = DebugSessionController()
    controller.start(
        _FakeDebuggerService(),
        source_path=Path("demo.cbl"),
        document_id=uuid4(),
    )

    with pytest.raises(DebugSessionError):
        controller.start(
            _FakeDebuggerService(),
            source_path=Path("other.cbl"),
            document_id=uuid4(),
        )


def test_stop_clears_session_state(qapp) -> None:
    controller = DebugSessionController()
    service = _FakeDebuggerService()
    controller.start(
        service,
        source_path=Path("demo.cbl"),
        document_id=uuid4(),
    )

    controller.stop()

    assert service.stop_called is True
    assert controller.is_active is False
    assert controller.source_path is None
    assert controller.document_id is None


def test_add_breakpoint_is_idempotent_for_an_already_synced_line(
    qapp,
) -> None:
    controller = DebugSessionController()
    service = _FakeDebuggerService()
    controller.start(
        service,
        source_path=Path("demo.cbl"),
        document_id=uuid4(),
        breakpoint_lines=(10,),
    )

    controller.add_breakpoint(10)

    assert service.added_breakpoints == [("demo.cbl", 10)]


def test_remove_breakpoint_removes_the_real_gdb_breakpoint(qapp) -> None:
    controller = DebugSessionController()
    service = _FakeDebuggerService()
    controller.start(
        service,
        source_path=Path("demo.cbl"),
        document_id=uuid4(),
        breakpoint_lines=(10,),
    )

    controller.remove_breakpoint(10)

    assert service.removed_breakpoint_numbers == [1]

    # Removing a line that was never synced is a harmless no-op.
    controller.remove_breakpoint(999)
    assert service.removed_breakpoint_numbers == [1]


def test_sync_breakpoints_adds_and_removes_the_diff(qapp) -> None:
    controller = DebugSessionController()
    service = _FakeDebuggerService()
    controller.start(
        service,
        source_path=Path("demo.cbl"),
        document_id=uuid4(),
        breakpoint_lines=(10, 20),
    )

    controller.sync_breakpoints((20, 30))

    assert service.removed_breakpoint_numbers == [1]
    assert service.added_breakpoints == [
        ("demo.cbl", 10),
        ("demo.cbl", 20),
        ("demo.cbl", 30),
    ]


def test_pass_through_methods_require_an_active_session(qapp) -> None:
    controller = DebugSessionController()

    with pytest.raises(DebugSessionError):
        controller.continue_()

    with pytest.raises(DebugSessionError):
        controller.add_breakpoint(1)


def test_stopped_signal_forwards_the_service_callback(qapp) -> None:
    controller = DebugSessionController()
    service = _FakeDebuggerService()
    controller.start(
        service,
        source_path=Path("demo.cbl"),
        document_id=uuid4(),
    )

    received = []
    controller.stopped.connect(received.append)

    assert service.stopped_callback is not None
    service.stopped_callback("a-stopped-event")

    assert received == ["a-stopped-event"]
