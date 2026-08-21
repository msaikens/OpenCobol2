"""Session orchestration tying the GDB adapter to COBOL-aware value decoding.

`DebuggerService` is the one Qt-independent object the GUI layer (tasks
#113-#115) drives: it owns a `GdbAdapter`, knows how to map a COBOL data
name to its raw memory location (via the generated-header symbol map
from `gnucobol_symbols`) and decode it (via `cobol_values`), and
translates raw MI records into the domain models from `models.py`.

Deliberately out of scope here (left for task #115, per the empirically
observed GnuCOBOL behavior that stepping can land in the compiler's own
runtime frames): filtering step commands to stay within `.cbl` frames.
This service exposes plain single-step primitives and leaves any
"smart stepping" policy to its caller.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from opencobol2.debugger.cobol_values import (
    DataUsage,
    PictureSpec,
    decode_field_value,
    parse_picture_spec,
    usage_from_clause_keyword,
)
from opencobol2.debugger.gdb_adapter import (
    GdbAdapter,
    GdbAdapterError,
    GdbNotRunningError,
)
from opencobol2.debugger.gnucobol_symbols import (
    GeneratedFieldSymbol,
    parse_generated_symbol_map,
)
from opencobol2.debugger.mi_protocol import MIRecord, MIValue
from opencobol2.debugger.models import (
    Breakpoint,
    DebuggerState,
    MemoryBytes,
    RegisterValue,
    StackFrame,
    StopReason,
    StoppedEvent,
    ThreadInfo,
    Variable,
)
from opencobol2.language import DataItemNode, SymbolTable, render_clause_tokens


class DebuggerServiceError(RuntimeError):
    """Raised for COBOL-debugging-specific failures (not raw MI/GDB errors)."""


_USAGE_CLAUSE_KEYWORDS = frozenset(
    {
        "DISPLAY",
        "COMP",
        "COMPUTATIONAL",
        "COMP-1",
        "COMPUTATIONAL-1",
        "COMP-2",
        "COMPUTATIONAL-2",
        "COMP-3",
        "COMPUTATIONAL-3",
        "COMP-4",
        "COMPUTATIONAL-4",
        "COMP-5",
        "COMPUTATIONAL-5",
        "BINARY",
        "PACKED-DECIMAL",
    },
)


def resolve_picture_and_usage(
    item: DataItemNode,
) -> tuple[PictureSpec, DataUsage]:
    """Determine an item's decoded shape from its PIC/USAGE clauses.

    Defaults to an alphanumeric picture and `DISPLAY` usage when a
    clause is absent, matching COBOL's own implicit defaults.

    This looks for a `USAGE` keyword clause among `item.clauses`
    directly, rather than for a `USAGE` clause carrying the specific
    usage as a token, because the parser splits clauses on any
    recognized clause keyword, and every USAGE keyword (`COMP-3`,
    `BINARY`, ...) is itself one of those -- so `USAGE COMP-3` always
    yields a bare "USAGE" clause followed by its own separate "COMP-3"
    clause, never a "USAGE" clause carrying the keyword as a second
    token.

    :param item: The data item whose PIC/USAGE clauses to inspect.
    :returns: A tuple of the item's decoded `PictureSpec` and
        `DataUsage`.
    """

    picture = PictureSpec(is_numeric=False)
    usage = DataUsage.DISPLAY

    for clause in item.clauses:
        if clause.keyword in ("PIC", "PICTURE"):
            picture = parse_picture_spec(
                render_clause_tokens(clause.tokens),
            )
        elif clause.keyword in _USAGE_CLAUSE_KEYWORDS:
            usage = usage_from_clause_keyword(clause.keyword)

    return picture, usage


def _stack_frame_from_mi(
    frame: Mapping[str, MIValue],
    *,
    default_level: int = 0,
) -> StackFrame:
    """Build a :class:`StackFrame` from one raw MI frame tuple.

    :param frame: The raw MI `frame` tuple, as returned inline in
        breakpoint/stop records or as one entry of `-stack-list-frames`.
    :param default_level: The stack level to use when `frame` has no
        `level` field.
    :returns: The decoded :class:`StackFrame`.
    """

    level_raw = frame.get("level")
    file_raw = frame.get("fullname") or frame.get("file")
    line_raw = frame.get("line")

    return StackFrame(
        level=int(level_raw) if level_raw is not None else default_level,
        function_name=str(frame.get("func", "??")),
        source_path=Path(file_raw) if file_raw else None,
        line=int(line_raw) if line_raw else None,
        address=frame.get("addr"),
    )


def _breakpoint_from_mi(bkpt: Mapping[str, MIValue]) -> Breakpoint:
    """Build a :class:`Breakpoint` from a raw MI `bkpt` tuple.

    :param bkpt: The raw MI `bkpt` tuple, as returned by
        `-break-insert`.
    :returns: The decoded :class:`Breakpoint`.
    """

    source_path = bkpt.get("fullname") or bkpt.get("file") or ""

    return Breakpoint(
        number=int(bkpt["number"]),
        source_path=Path(source_path),
        line=int(bkpt["line"]),
        enabled=bkpt.get("enabled") == "y",
        function_name=bkpt.get("func"),
        hit_count=int(bkpt.get("times", 0)),
    )


def _stopped_event_from_record(record: MIRecord) -> StoppedEvent:
    """Build a :class:`StoppedEvent` from a raw MI `*stopped` record.

    `exit_code` is parsed as base-8 because GDB reports the inferior's
    exit code in plain octal digits with no `"0o"` prefix (e.g. `"052"`
    for decimal 42) -- verified against a real
    `*stopped,reason="exited",exit-code="052"` record.

    :param record: The raw MI `*stopped` async record to decode.
    :returns: The decoded :class:`StoppedEvent`.
    """

    reason = StopReason.from_gdb_reason(record.get("reason"))
    thread_id_raw = record.get("thread-id")
    frame_raw = record.get("frame")
    exit_code_raw = record.get("exit-code")

    return StoppedEvent(
        reason=reason,
        thread_id=(
            int(thread_id_raw)
            if isinstance(thread_id_raw, str) and thread_id_raw.isdigit()
            else None
        ),
        frame=(
            _stack_frame_from_mi(frame_raw)
            if isinstance(frame_raw, Mapping)
            else None
        ),
        exit_code=(
            int(exit_code_raw, 8)
            if isinstance(exit_code_raw, str)
            else None
        ),
    )


def _escape_mi_expression(expression: str) -> str:
    """Escape an expression for safe embedding in a quoted MI command.

    :param expression: The raw expression text to escape.
    :returns: `expression` with backslashes and double quotes escaped.
    """

    return expression.replace("\\", "\\\\").replace('"', '\\"')


_COBOL_SOURCE_EXTENSIONS = frozenset({".cbl", ".cob"})


class DebuggerService:
    """Owns one GDB-backed debug session for a compiled COBOL program.

    :ivar _adapter: The underlying `GdbAdapter` this service drives.
    :ivar _state: The session's current lifecycle state, exposed via
        the `state` property.
    :ivar _symbol_table: The active program's analyzed semantic symbol
        table, set by `start_session`; `None` before a session starts.
    :ivar _field_symbols: The active program's generated-header field
        symbol map (COBOL data name to raw buffer location), set by
        `start_session`.
    :ivar _breakpoints: Every breakpoint currently known to this
        session, keyed by breakpoint number.
    :ivar _stopped_callbacks: Every callback registered via
        `on_stopped`, fired whenever the debugged program pauses.
    :ivar _stop_event: Signaled by `_handle_stopped` each time a
        `*stopped` record arrives, used by `_smart_step` to wait for
        one internal step to complete.
    :ivar _last_stopped_event: The most recently decoded
        :class:`StoppedEvent`, read by `_smart_step` once `_stop_event`
        is signaled.
    :ivar _suspend_stopped_callbacks: While `True`, `_handle_stopped`
        updates session state but does not fire `_stopped_callbacks`;
        set during `_smart_step` so intermediate internal steps stay
        silent and only the final landing fires a callback.
    """

    def __init__(
        self,
        *,
        gdb_executable: str = "gdb",
        command_timeout_seconds: float = 10.0,
    ) -> None:
        """Construct a debugger service with no active session yet.

        :param gdb_executable: The GDB executable name or path to
            launch for this session.
        :param command_timeout_seconds: How long to wait for a reply to
            any single MI command before raising.
        :returns: None.
        """

        self._adapter = GdbAdapter(
            gdb_executable=gdb_executable,
            command_timeout_seconds=command_timeout_seconds,
        )
        self._state = DebuggerState.NOT_STARTED
        self._symbol_table: SymbolTable | None = None
        self._field_symbols: dict[str, GeneratedFieldSymbol] = {}
        self._breakpoints: dict[int, Breakpoint] = {}
        self._stopped_callbacks: list[Callable[[StoppedEvent], None]] = []
        self._stop_event = threading.Event()
        self._last_stopped_event: StoppedEvent | None = None
        self._suspend_stopped_callbacks = False

        self._adapter.on_stopped(self._handle_stopped)

    @property
    def state(self) -> DebuggerState:
        """Return the current lifecycle state of this session."""

        return self._state

    def on_stopped(
        self,
        callback: Callable[[StoppedEvent], None],
    ) -> None:
        """Register a callback fired with a `StoppedEvent` on every pause."""

        self._stopped_callbacks.append(callback)

    def start_session(
        self,
        executable_path: Path,
        *,
        source_path: Path,
        symbol_table: SymbolTable,
        environment: Mapping[str, str] | None = None,
        header_paths: Sequence[Path] | None = None,
    ) -> None:
        """Spawn GDB against a compiled COBOL program, ready for breakpoints.

        `symbol_table` is this program's already-analyzed semantic
        symbol table (see `opencobol2.language.analyze_compilation_unit`),
        used to resolve a data name's PICTURE/USAGE when reading its
        value. `header_paths` defaults to the `<source>.c.l.h` /
        `<source>.c.h` files `cobc -g -debug` leaves next to the
        source file.
        """

        if header_paths is None:
            header_paths = (
                source_path.with_name(f"{source_path.stem}.c.l.h"),
                source_path.with_name(f"{source_path.stem}.c.h"),
            )

        header_texts = tuple(
            path.read_text()
            for path in header_paths
            if path.is_file()
        )

        self._field_symbols = parse_generated_symbol_map(*header_texts)
        self._symbol_table = symbol_table
        self._adapter.start(executable_path, environment=environment)
        self._state = DebuggerState.PAUSED

    def _send_command(self, command: str) -> MIRecord:
        """Send one MI command, translating adapter-layer failures.

        Editor §DebuggerLogic-6: every caller of
        `GdbAdapter.send_command` in this class used to leave
        `GdbAdapterError`/`GdbNotRunningError`/`TimeoutError` -- three
        exception types with no relation to this class's own
        `DebuggerServiceError` -- to propagate straight through. A
        caller that (reasonably) only catches `DebuggerServiceError`
        around a debugger call would be surprised by a different,
        adapter-layer exception type for what is, from a COBOL-
        debugging caller's perspective, the identical "the debugger
        command failed" outcome.
        """

        try:
            return self._adapter.send_command(
                command,
            )
        except (
            GdbAdapterError,
            GdbNotRunningError,
            TimeoutError,
        ) as error:
            raise DebuggerServiceError(
                str(
                    error,
                ),
            ) from error

    def add_breakpoint(self, source_file: str, line: int) -> Breakpoint:
        """Insert a breakpoint at a source file/line and return it."""

        result = self._send_command(
            f"-break-insert {source_file}:{line}",
        )
        breakpoint_ = _breakpoint_from_mi(result.get("bkpt", {}))
        self._breakpoints[breakpoint_.number] = breakpoint_
        return breakpoint_

    def remove_breakpoint(self, number: int) -> None:
        """Delete a previously inserted breakpoint by its number."""

        self._send_command(f"-break-delete {number}")
        self._breakpoints.pop(number, None)

    def breakpoints(self) -> tuple[Breakpoint, ...]:
        """Return every breakpoint currently known to this session."""

        return tuple(self._breakpoints.values())

    def run(self) -> None:
        """Start executing the debugged program from the beginning."""

        self._send_command("-exec-run")
        self._state = DebuggerState.RUNNING

    def continue_(self) -> None:
        """Resume a paused program."""

        self._send_command("-exec-continue")
        self._state = DebuggerState.RUNNING

    def step_over(self) -> None:
        """Step one source line, stepping over any call."""

        self._send_command("-exec-next")
        self._state = DebuggerState.RUNNING

    def step_into(self) -> None:
        """Step one source line, stepping into any call."""

        self._send_command("-exec-step")
        self._state = DebuggerState.RUNNING

    def step_out(self) -> None:
        """Run until the current function returns."""

        self._send_command("-exec-finish")
        self._state = DebuggerState.RUNNING

    def step_over_cobol_line(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_internal_steps: int = 50,
    ) -> StoppedEvent:
        """Step over, transparently skipping GnuCOBOL's own runtime frames.

        A single `-exec-next` can land inside GnuCOBOL's generated
        frame-management code rather than the next COBOL source line
        (verified against a real session) -- this repeats `step_over()`
        internally until execution reaches a `.cbl`/`.cob` frame (or the
        program exits), firing exactly one `on_stopped` callback for the
        result rather than one per intermediate internal step.
        """

        return self._smart_step(
            self.step_over,
            timeout_seconds=timeout_seconds,
            max_internal_steps=max_internal_steps,
        )

    def step_into_cobol_line(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_internal_steps: int = 1000,
    ) -> StoppedEvent:
        """Step into, transparently skipping GnuCOBOL's own runtime frames.

        See `step_over_cobol_line` for why this internal repeat-and-check
        loop is necessary.

        Editor §DebuggerLogic-5: unlike `step_over_cobol_line` (which
        skips a called subprogram's internals entirely via `-exec-next`'s
        own return-address breakpoint), stepping *into* a real `CALL`
        single-steps through every one of GnuCOBOL's runtime
        frame-management instructions in the callee's prologue --
        measured directly against a real dynamically-loaded subprogram
        at 19 raw steps just to reach the callee's `PROCEDURE DIVISION`
        header line, and 51-500 to reach its first real statement. The
        previous default of 50 reliably failed on this exact, ordinary
        scenario with a raw internal error instead of a normal landing.
        """

        return self._smart_step(
            self.step_into,
            timeout_seconds=timeout_seconds,
            max_internal_steps=max_internal_steps,
        )

    def _smart_step(
        self,
        step_fn: Callable[[], None],
        *,
        timeout_seconds: float,
        max_internal_steps: int,
    ) -> StoppedEvent:
        self._suspend_stopped_callbacks = True

        try:
            event: StoppedEvent | None = None

            for _ in range(max_internal_steps):
                self._stop_event.clear()
                step_fn()

                if not self._stop_event.wait(timeout_seconds):
                    raise DebuggerServiceError(
                        "Timed out waiting for a step to complete.",
                    )

                event = self._last_stopped_event
                assert event is not None

                if event.reason in (
                    StopReason.EXITED,
                    StopReason.EXITED_NORMALLY,
                ):
                    break

                frame = event.frame

                if (
                    frame is not None
                    and frame.source_path is not None
                    and frame.source_path.suffix.lower()
                    in _COBOL_SOURCE_EXTENSIONS
                ):
                    break
            else:
                raise DebuggerServiceError(
                    "Never reached a COBOL source line after "
                    f"{max_internal_steps} internal steps.",
                )
        finally:
            self._suspend_stopped_callbacks = False

        for callback in self._stopped_callbacks:
            callback(event)

        return event

    def stop(self) -> None:
        """Terminate the debug session."""

        self._adapter.terminate()
        self._state = DebuggerState.EXITED

    def stack_frames(self) -> tuple[StackFrame, ...]:
        """Return the current thread's call stack, innermost first."""

        result = self._send_command("-stack-list-frames")
        stack = result.get("stack", ())

        return tuple(
            _stack_frame_from_mi(entry["frame"]) for entry in stack
        )

    def threads(self) -> tuple[ThreadInfo, ...]:
        """Return every thread in the debugged process."""

        result = self._send_command("-thread-info")
        raw_threads = result.get("threads", ())

        threads = []

        for raw_thread in raw_threads:
            frame_raw = raw_thread.get("frame")
            threads.append(
                ThreadInfo(
                    thread_id=int(raw_thread["id"]),
                    state=raw_thread.get("state", ""),
                    frame=(
                        _stack_frame_from_mi(frame_raw)
                        if isinstance(frame_raw, Mapping)
                        else None
                    ),
                ),
            )

        return tuple(threads)

    def registers(self) -> tuple[RegisterValue, ...]:
        """Return every named CPU register's current value (hex format)."""

        names_result = self._send_command(
            "-data-list-register-names",
        )
        names = names_result.get("register-names", ())

        values_result = self._send_command(
            "-data-list-register-values x",
        )
        raw_values = values_result.get("register-values", ())

        registers = []

        for entry in raw_values:
            index = int(entry["number"])

            if index >= len(names) or not names[index]:
                continue

            registers.append(
                RegisterValue(name=names[index], value=entry["value"]),
            )

        return tuple(registers)

    def read_memory(self, address: str, length: int) -> MemoryBytes:
        """Read `length` raw bytes starting at a GDB-evaluable address."""

        result = self._send_command(
            f"-data-read-memory-bytes {address} {length}",
        )
        entry = result.get("memory")[0]

        return MemoryBytes(
            address=int(entry["begin"], 16),
            data=bytes.fromhex(entry["contents"]),
        )

    def evaluate_expression(self, expression: str) -> str:
        """Evaluate an arbitrary GDB expression and return its display text."""

        escaped = _escape_mi_expression(expression)
        result = self._send_command(
            f'-data-evaluate-expression "{escaped}"',
        )
        return result.get("value", "")

    def read_variable(self, cobol_name: str) -> Variable:
        """Read and decode one COBOL data item's live value.

        Combines the generated-header symbol map (name -> raw buffer),
        a live memory read, and the item's PICTURE/USAGE clauses (from
        the session's symbol table) to produce the value COBOL itself
        would show -- not GDB's raw byte view.
        """

        if self._symbol_table is None:
            raise DebuggerServiceError("No active debug session.")

        normalized_name = cobol_name.strip().upper()
        field_symbol = self._field_symbols.get(normalized_name)

        if field_symbol is None:
            raise DebuggerServiceError(
                f"{cobol_name!r} has no known memory location "
                "(was it compiled with `cobc -g -debug`?).",
            )

        data_symbols = self._symbol_table.find_data_symbols(normalized_name)

        if not data_symbols:
            raise DebuggerServiceError(
                f"{cobol_name!r} is not a known data item.",
            )

        picture, usage = resolve_picture_and_usage(data_symbols[0].item)

        memory_result = self._send_command(
            "-data-read-memory-bytes "
            f"{field_symbol.buffer_variable} {field_symbol.byte_length}",
        )
        raw_bytes = bytes.fromhex(
            memory_result.get("memory")[0]["contents"],
        )
        decoded_value = decode_field_value(
            raw_bytes,
            picture=picture,
            usage=usage,
        )

        return Variable(
            name=cobol_name,
            value=decoded_value,
            type_name=usage.value,
        )

    def _handle_stopped(self, record: MIRecord) -> None:
        event = _stopped_event_from_record(record)
        self._state = (
            DebuggerState.EXITED
            if event.reason
            in (StopReason.EXITED, StopReason.EXITED_NORMALLY)
            else DebuggerState.PAUSED
        )
        self._last_stopped_event = event
        self._stop_event.set()

        if self._suspend_stopped_callbacks:
            return

        for callback in self._stopped_callbacks:
            callback(event)
