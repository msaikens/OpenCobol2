"""A thin, thread-safe Qt bridge around one `DebuggerService` session.

`DebuggerService.on_stopped` callbacks can fire from GDB's background
reader thread (for a plain `continue_()`/`run()`) or synchronously from
the calling thread (for a smart-step's own suppressed-then-replayed
callback) -- see `opencobol2.debugger.service`. Connecting `stopped`
directly to `service.on_stopped` relies on Qt's own auto-connection
behavior to make both cases safe: PySide6 detects whether the emitting
thread differs from a connected slot's receiver thread and transparently
switches to a queued (deferred, main-thread) delivery when it does,
falling back to a plain direct call otherwise. This is the standard,
documented way to get worker-thread events onto the GUI thread without
hand-rolled `QMetaObject.invokeMethod` plumbing.

This controller does not own toolchain discovery, compilation, or
`DebuggerService` construction -- see `opencobol2.gui.debug_commands`
for that. It only wraps an already-started service: Qt signal bridging,
breakpoint-sync bookkeeping against one source file, and pass-through
convenience methods, kept separate so it can be unit-tested with a
lightweight stand-in rather than a real GDB session.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QObject, Signal

from opencobol2.debugger.models import (
    Breakpoint,
    MemoryBytes,
    RegisterValue,
    StackFrame,
    StoppedEvent,
    ThreadInfo,
    Variable,
)
from opencobol2.debugger.service import DebuggerService


class DebugSessionError(RuntimeError):
    """Raised for controller-level session-state errors."""


class DebugSessionController(QObject):
    """Owns the GUI-facing lifecycle of at most one active debug session."""

    stopped = Signal(object)
    """Fired with a `StoppedEvent` on every pause (queued across threads)."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an idle controller; call `start()` to attach a session."""

        super().__init__(parent)

        self._service: DebuggerService | None = None
        self._source_path: Path | None = None
        self._document_id: UUID | None = None
        self._synced_breakpoints: dict[int, int] = {}

    @property
    def is_active(self) -> bool:
        """Return whether a debug session is currently attached."""

        return self._service is not None

    @property
    def source_path(self) -> Path | None:
        """Return the source file the active session is debugging, if any."""

        return self._source_path

    @property
    def document_id(self) -> UUID | None:
        """Return the editor document ID being debugged, if any."""

        return self._document_id

    def start(
        self,
        service: DebuggerService,
        *,
        source_path: Path,
        document_id: UUID,
        breakpoint_lines: Sequence[int] = (),
    ) -> None:
        """Attach an already-started `DebuggerService` and run it.

        `service.start_session(...)` must already have been called by
        the caller (see `opencobol2.gui.debug_commands`) -- this just
        takes ownership, seeds breakpoints, wires the `stopped` signal,
        and starts execution.
        """

        if self.is_active:
            raise DebugSessionError(
                "A debug session is already active.",
            )

        self._service = service
        self._source_path = source_path
        self._document_id = document_id
        self._synced_breakpoints = {}

        service.on_stopped(self.stopped.emit)

        for line in breakpoint_lines:
            self.add_breakpoint(line)

        service.run()

    def stop(self) -> None:
        """Terminate the active session, if any."""

        if self._service is not None:
            self._service.stop()

        self._service = None
        self._source_path = None
        self._document_id = None
        self._synced_breakpoints = {}

    def add_breakpoint(self, line: int) -> None:
        """Insert a real breakpoint at a line in the debugged source file."""

        service = self._require_service()

        if self._source_path is None or line in self._synced_breakpoints:
            return

        breakpoint_ = service.add_breakpoint(
            self._source_path.name,
            line,
        )
        self._synced_breakpoints[line] = breakpoint_.number

    def remove_breakpoint(self, line: int) -> None:
        """Remove a previously-synced breakpoint at a line, if present."""

        service = self._require_service()

        if line not in self._synced_breakpoints:
            return

        number = self._synced_breakpoints.pop(line)
        service.remove_breakpoint(number)

    def sync_breakpoints(self, current_lines: Sequence[int]) -> None:
        """Reconcile GDB's breakpoints against a source file's current set."""

        current = set(current_lines)

        for line in tuple(self._synced_breakpoints):
            if line not in current:
                self.remove_breakpoint(line)

        for line in current:
            if line not in self._synced_breakpoints:
                self.add_breakpoint(line)

    def breakpoints(self) -> tuple[Breakpoint, ...]:
        """Return every breakpoint known to the active session."""

        return self._require_service().breakpoints()

    def continue_(self) -> None:
        """Resume a paused program."""

        self._require_service().continue_()

    def step_over(self) -> StoppedEvent:
        """Step over one COBOL source line."""

        return self._require_service().step_over_cobol_line()

    def step_into(self) -> StoppedEvent:
        """Step into one COBOL source line."""

        return self._require_service().step_into_cobol_line()

    def step_out(self) -> None:
        """Run until the current function returns."""

        self._require_service().step_out()

    def stack_frames(self) -> tuple[StackFrame, ...]:
        """Return the current thread's call stack."""

        return self._require_service().stack_frames()

    def threads(self) -> tuple[ThreadInfo, ...]:
        """Return every thread in the debugged process."""

        return self._require_service().threads()

    def registers(self) -> tuple[RegisterValue, ...]:
        """Return every CPU register's current value."""

        return self._require_service().registers()

    def read_memory(self, address: str, length: int) -> MemoryBytes:
        """Read raw bytes starting at a GDB-evaluable address."""

        return self._require_service().read_memory(address, length)

    def evaluate_expression(self, expression: str) -> str:
        """Evaluate an arbitrary GDB expression."""

        return self._require_service().evaluate_expression(expression)

    def read_variable(self, cobol_name: str) -> Variable:
        """Read and decode one live COBOL variable's value."""

        return self._require_service().read_variable(cobol_name)

    def _require_service(self) -> DebuggerService:
        if self._service is None:
            raise DebugSessionError("No active debug session.")

        return self._service
