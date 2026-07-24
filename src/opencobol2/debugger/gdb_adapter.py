"""A thin adapter around a real `gdb --interpreter=mi2` subprocess.

Deliberately mechanical: this module only knows how to spawn GDB, send
raw MI command strings, and correlate results / dispatch async and
stream records to observers. It has no COBOL- or debugging-domain-
specific concepts (breakpoints, stack frames, ...) -- those live in
`opencobol2.debugger.service`, which drives this adapter and translates
between MI records and the domain models in `opencobol2.debugger.models`.

`send_command` looks synchronous from the caller's side even though MI
is fundamentally asynchronous: unrelated async records (a breakpoint
hit, a new thread, console output) can interleave with any command's
own response at any time. Each command sent gets an auto-incrementing
numeric token that GDB echoes back on its result record
(`5-break-insert ...` -> `5^done,...`), which is what makes reliable
correlation possible regardless of what else arrives in between. A
background thread continuously reads and parses GDB's stdout, routing
each parsed record either to whichever pending command's token it
matches, or to registered observer callbacks for anything that isn't a
correlated result.
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from opencobol2.debugger.mi_protocol import (
    MIParseError,
    MIRecord,
    MIRecordKind,
    parse_mi_line,
)


class GdbAdapterError(RuntimeError):
    """Raised when GDB reports an error result (`^error`) for a command."""


class GdbNotRunningError(RuntimeError):
    """Raised when a command is sent to an adapter that isn't running."""


class _PendingCommand:
    """Tracks one in-flight command awaiting its correlated result record."""

    def __init__(
        self,
    ) -> None:
        self.event = threading.Event()
        self.record: MIRecord | None = None


class GdbAdapter:
    """A live connection to one `gdb --interpreter=mi2` process."""

    def __init__(
        self,
        *,
        gdb_executable: str = "gdb",
        command_timeout_seconds: float = 10.0,
    ) -> None:
        """Create an adapter; call `start()` to actually spawn GDB."""

        self._gdb_executable = gdb_executable
        self._command_timeout_seconds = (
            command_timeout_seconds
        )
        self._process: (
            subprocess.Popen[str] | None
        ) = None
        self._reader_thread: (
            threading.Thread | None
        ) = None
        self._next_token = 1
        self._token_lock = threading.Lock()
        self._pending: dict[
            int,
            _PendingCommand,
        ] = {}
        self._pending_lock = threading.Lock()
        self._stopped_callbacks: list[
            Callable[[MIRecord], None]
        ] = []
        self._console_callbacks: list[
            Callable[[str], None]
        ] = []
        self._notify_callbacks: list[
            Callable[[MIRecord], None]
        ] = []

    @property
    def is_running(
        self,
    ) -> bool:
        """Return whether the GDB process is alive."""

        return (
            self._process is not None
            and self._process.poll() is None
        )

    def start(
        self,
        program_path: Path,
        *,
        arguments: Sequence[str] = (),
        environment: Mapping[str, str] | None = None,
    ) -> None:
        """Spawn GDB against a debug-symbol-enabled program and start reading.

        `environment`, if given, replaces the process environment GDB
        (and the inferior it launches) sees -- needed e.g. so a
        GnuCOBOL-compiled inferior can find its runtime DLLs on `PATH`.
        Defaults to inheriting this process's own environment.
        """

        if self._process is not None:
            raise RuntimeError(
                "GdbAdapter is already started."
            )

        self._process = subprocess.Popen(
            [
                self._gdb_executable,
                "--interpreter=mi2",
                "--quiet",
                "--nx",
                str(
                    program_path,
                ),
                *arguments,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=(
                dict(environment)
                if environment is not None
                else None
            ),
        )
        self._reader_thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
        )
        self._reader_thread.start()

    def on_stopped(
        self,
        callback: Callable[
            [MIRecord],
            None,
        ],
    ) -> None:
        """Register a callback for every `*stopped` exec-async record."""

        self._stopped_callbacks.append(
            callback,
        )

    def on_console_output(
        self,
        callback: Callable[
            [str],
            None,
        ],
    ) -> None:
        """Register a callback for every console-stream (`~`) message."""

        self._console_callbacks.append(
            callback,
        )

    def on_notify(
        self,
        callback: Callable[
            [MIRecord],
            None,
        ],
    ) -> None:
        """Register a callback for every async record (exec/notify/status)."""

        self._notify_callbacks.append(
            callback,
        )

    def send_command(
        self,
        command: str,
    ) -> MIRecord:
        """Send one MI command (e.g. `-break-insert main`) and await its result.

        Raises `GdbNotRunningError` if the process isn't running,
        `TimeoutError` if no correlated result arrives in time, and
        `GdbAdapterError` if GDB's result is `^error`.
        """

        if not self.is_running:
            raise GdbNotRunningError(
                "GDB is not running."
            )

        with self._token_lock:
            token = self._next_token
            self._next_token += 1

        pending = _PendingCommand()

        with self._pending_lock:
            self._pending[token] = pending

        assert self._process is not None
        assert self._process.stdin is not None

        self._process.stdin.write(
            f"{token}{command}\n",
        )
        self._process.stdin.flush()

        if not pending.event.wait(
            self._command_timeout_seconds,
        ):
            with self._pending_lock:
                self._pending.pop(
                    token,
                    None,
                )

            raise TimeoutError(
                f"GDB did not respond to {command!r} "
                f"within {self._command_timeout_seconds}s."
            )

        record = pending.record
        assert record is not None

        if record.klass == "error":
            raise GdbAdapterError(
                str(
                    record.get(
                        "msg",
                        "Unknown GDB error.",
                    )
                )
            )

        return record

    def terminate(
        self,
    ) -> None:
        """Ask GDB to exit, falling back to killing it if it doesn't."""

        if self._process is None:
            return

        try:
            if self.is_running:
                assert (
                    self._process.stdin
                    is not None
                )
                self._process.stdin.write(
                    "-gdb-exit\n",
                )
                self._process.stdin.flush()

            self._process.wait(
                timeout=5,
            )
        except Exception:
            self._process.kill()
        finally:
            if (
                self._reader_thread
                is not None
            ):
                self._reader_thread.join(
                    timeout=5,
                )

    def _read_loop(
        self,
    ) -> None:
        assert self._process is not None
        assert self._process.stdout is not None

        for raw_line in self._process.stdout:
            line = raw_line.rstrip(
                "\r\n",
            )

            try:
                record = parse_mi_line(
                    line,
                )
            except MIParseError:
                # A malformed or unrecognized line from GDB shouldn't
                # ever crash this long-lived background thread.
                continue

            if record is None:
                continue

            self._dispatch(
                record,
            )

    def _dispatch(
        self,
        record: MIRecord,
    ) -> None:
        if (
            record.kind
            == MIRecordKind.RESULT
            and record.token is not None
        ):
            with self._pending_lock:
                pending = self._pending.pop(
                    record.token,
                    None,
                )

            if pending is not None:
                pending.record = record
                pending.event.set()
                return

        if (
            record.kind
            == MIRecordKind.EXEC_ASYNC
            and record.klass == "stopped"
        ):
            for (
                callback
            ) in self._stopped_callbacks:
                callback(
                    record,
                )

        if record.kind in (
            MIRecordKind.NOTIFY_ASYNC,
            MIRecordKind.EXEC_ASYNC,
            MIRecordKind.STATUS_ASYNC,
        ):
            for (
                callback
            ) in self._notify_callbacks:
                callback(
                    record,
                )

        if (
            record.kind
            == MIRecordKind.CONSOLE_STREAM
            and record.text
        ):
            for (
                callback
            ) in self._console_callbacks:
                callback(
                    record.text,
                )
