"""Qt-independent debugger domain models.

Deliberately independent of any specific debugger backend -- these
types describe what a debug session *is* (its state, breakpoints,
stack frames, variables), not how one particular adapter talks to a
debugger process. `opencobol2.debugger.gdb_adapter` is the only module
that knows about GDB or the MI protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class DebuggerState(StrEnum):
    """The lifecycle state of one debug session."""

    NOT_STARTED = "not-started"
    RUNNING = "running"
    PAUSED = "paused"
    EXITED = "exited"


class StopReason(StrEnum):
    """Why a running debug session paused.

    Values match GDB/MI's own `reason=` strings directly, so converting
    a raw MI value is a simple lookup (see `from_gdb_reason`) rather
    than a translation table -- `OTHER` covers any reason this codebase
    doesn't specifically model (GDB has several more, e.g. watchpoint
    variants, that aren't yet surfaced as their own UI-relevant state).
    """

    BREAKPOINT_HIT = "breakpoint-hit"
    STEP_COMPLETED = "end-stepping-range"
    FUNCTION_FINISHED = "function-finished"
    SIGNAL_RECEIVED = "signal-received"
    EXITED_NORMALLY = "exited-normally"
    EXITED = "exited"
    OTHER = "other"

    @classmethod
    def from_gdb_reason(
        cls,
        raw_reason: str | None,
    ) -> "StopReason":
        """Convert a raw MI `reason=` value, falling back to `OTHER`."""

        if raw_reason is None:
            return cls.OTHER

        try:
            return cls(
                raw_reason,
            )
        except ValueError:
            return cls.OTHER


@dataclass(frozen=True, slots=True, kw_only=True)
class Breakpoint:
    """One breakpoint known to the debugger backend."""

    number: int
    source_path: Path
    line: int
    enabled: bool = True
    function_name: str | None = None
    hit_count: int = 0

    def __post_init__(self) -> None:
        """Validate breakpoint invariants and normalize the source path."""

        if self.number <= 0:
            raise ValueError(
                "Breakpoint number must be positive."
            )

        if self.line <= 0:
            raise ValueError(
                "Breakpoint line must be positive."
            )

        if self.hit_count < 0:
            raise ValueError(
                "Breakpoint hit count must not be negative."
            )

        object.__setattr__(
            self,
            "source_path",
            Path(
                self.source_path,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class StackFrame:
    """One frame in a stopped thread's call stack."""

    level: int
    function_name: str
    source_path: Path | None = None
    line: int | None = None
    address: str | None = None

    def __post_init__(self) -> None:
        """Validate stack frame invariants and normalize the source path."""

        if self.level < 0:
            raise ValueError(
                "Stack frame level must not be negative."
            )

        if self.line is not None and self.line <= 0:
            raise ValueError(
                "Stack frame line must be positive."
            )

        if self.source_path is not None:
            object.__setattr__(
                self,
                "source_path",
                Path(
                    self.source_path,
                ),
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class Variable:
    """One local variable or argument in a stack frame."""

    name: str
    value: str
    is_argument: bool = False
    type_name: str | None = None

    def __post_init__(self) -> None:
        """Require a non-empty variable name."""

        if not self.name.strip():
            raise ValueError(
                "Variable name must not be empty."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ThreadInfo:
    """One thread in the debugged process."""

    thread_id: int
    state: str
    frame: StackFrame | None = None

    def __post_init__(self) -> None:
        """Require a positive thread ID."""

        if self.thread_id <= 0:
            raise ValueError(
                "Thread ID must be positive."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RegisterValue:
    """One CPU register's current value."""

    name: str
    value: str

    def __post_init__(self) -> None:
        """Require a non-empty register name."""

        if not self.name.strip():
            raise ValueError(
                "Register name must not be empty."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryBytes:
    """A contiguous read of raw memory starting at one address."""

    address: int
    data: bytes

    def __post_init__(self) -> None:
        """Require a non-negative memory address."""

        if self.address < 0:
            raise ValueError(
                "Memory address must not be negative."
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class WatchExpression:
    """One user-added expression tracked in the Watch panel."""

    expression: str
    value: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Require and normalize a non-empty expression."""

        normalized_expression = (
            self.expression.strip()
        )

        if not normalized_expression:
            raise ValueError(
                "Watch expression must not be empty."
            )

        object.__setattr__(
            self,
            "expression",
            normalized_expression,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class StoppedEvent:
    """Describes why and where a debug session just paused."""

    reason: StopReason
    thread_id: int | None = None
    frame: StackFrame | None = None
    exit_code: int | None = None
