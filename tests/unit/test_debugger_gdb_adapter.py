"""Unit tests for `GdbAdapter` against a fake `subprocess.Popen`.

`tests/integration/test_gdb_adapter.py` already exercises this module
against a real `gdb` subprocess -- this file covers scenarios that need
precise control over process lifecycle/timing (a raising observer
callback, the process dying mid-command, restarting after `terminate`)
that aren't practical to force deterministically against a real GDB
session.
"""

from __future__ import annotations

from pathlib import Path
import threading
import time

import pytest

import opencobol2.debugger.gdb_adapter as gdb_adapter
from opencobol2.debugger.gdb_adapter import (
    GdbAdapter,
    GdbNotRunningError,
)
from opencobol2.debugger.mi_protocol import (
    MIRecord,
    MIRecordKind,
)


class _FakeStdin:
    """A minimal stand-in for a `Popen` process's `stdin` pipe."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def write(self, text: str) -> None:
        self.written.append(text)

    def flush(self) -> None:
        pass


class _BlockingFakeProcess:
    """A fake Popen result whose `stdout` blocks until told to stop.

    Mirrors a real, live-but-quiet `gdb` subprocess: the reader thread
    stays parked in its `for raw_line in process.stdout` loop until
    either `kill()`/`wait()` (simulating GDB actually exiting) or
    `die()` (simulating the process dying unexpectedly) is called.
    """

    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stdout = self
        self._returncode: int | None = None
        self._stop_event = threading.Event()

    def __iter__(self) -> "_BlockingFakeProcess":
        return self

    def __next__(self) -> str:
        self._stop_event.wait()
        raise StopIteration

    def poll(self) -> int | None:
        return self._returncode

    def kill(self) -> None:
        self._returncode = -9
        self._stop_event.set()

    def wait(
        self,
        timeout: float | None = None,
    ) -> int:
        self._returncode = 0
        self._stop_event.set()
        return self._returncode

    def die(self) -> None:
        """Simulate the process dying unexpectedly, unlike a clean exit."""

        self._returncode = 1
        self._stop_event.set()


def test_dispatch_isolates_a_raising_stopped_callback() -> None:
    # Editor §DebuggerCore-1: an exception raised inside one registered
    # observer callback used to propagate straight out of `_dispatch`,
    # which would have killed the real reader thread permanently and
    # silently, and also would have prevented every other observer
    # registered for the same record from ever running.
    adapter = GdbAdapter()
    received: list[MIRecord] = []

    def raising_callback(
        record: MIRecord,
    ) -> None:
        raise RuntimeError("boom")

    adapter.on_stopped(raising_callback)
    adapter.on_stopped(received.append)

    record = MIRecord(
        kind=MIRecordKind.EXEC_ASYNC,
        klass="stopped",
    )

    adapter._dispatch(record)

    assert received == [record]


def test_dispatch_isolates_a_raising_notify_callback() -> None:
    adapter = GdbAdapter()
    received: list[MIRecord] = []

    adapter.on_notify(
        lambda record: (_ for _ in ()).throw(
            RuntimeError("boom"),
        )
    )
    adapter.on_notify(received.append)

    record = MIRecord(
        kind=MIRecordKind.NOTIFY_ASYNC,
        klass="thread-created",
    )

    adapter._dispatch(record)

    assert received == [record]


def test_dispatch_isolates_a_raising_console_callback() -> None:
    adapter = GdbAdapter()
    received: list[str] = []

    adapter.on_console_output(
        lambda text: (_ for _ in ()).throw(
            RuntimeError("boom"),
        )
    )
    adapter.on_console_output(received.append)

    record = MIRecord(
        kind=MIRecordKind.CONSOLE_STREAM,
        text="hello",
    )

    adapter._dispatch(record)

    assert received == ["hello"]


def test_start_pins_utf8_encoding_on_the_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Editor §DebuggerCore-3: without a pinned `encoding=`, decoding
    # falls back to the system's preferred encoding (`cp1252` on
    # Windows), silently mangling non-ASCII text.
    captured: dict[str, object] = {}

    class _EmptyProcess:
        def __init__(self) -> None:
            self.stdin = _FakeStdin()
            self.stdout: object = iter(())

    def fake_popen(
        args: object,
        **kwargs: object,
    ) -> _EmptyProcess:
        captured.update(kwargs)
        return _EmptyProcess()

    monkeypatch.setattr(
        gdb_adapter.subprocess,
        "Popen",
        fake_popen,
    )

    adapter = GdbAdapter()
    adapter.start(
        Path("program"),
    )

    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_send_command_raises_promptly_when_gdb_dies_while_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Editor §DebuggerCore-4: `send_command` used to check `is_running`
    # only once, before writing, then wait the *entire* configured
    # timeout even if the process died moments later -- wasting most
    # of the wait reporting a generic timeout instead of a fast,
    # specific "process died" signal.
    fake_process = _BlockingFakeProcess()
    monkeypatch.setattr(
        gdb_adapter.subprocess,
        "Popen",
        lambda *args, **kwargs: fake_process,
    )

    adapter = GdbAdapter(
        command_timeout_seconds=5.0,
    )
    adapter.start(
        Path("program"),
    )

    def kill_soon() -> None:
        time.sleep(0.3)
        fake_process.die()

    threading.Thread(
        target=kill_soon,
        daemon=True,
    ).start()

    started_at = time.monotonic()

    with pytest.raises(GdbNotRunningError):
        adapter.send_command(
            "-exec-continue",
        )

    elapsed_seconds = time.monotonic() - started_at

    assert elapsed_seconds < 2.0


def test_adapter_can_be_restarted_after_terminate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Editor §DebuggerCore-10: `start()`'s reuse guard raised
    # "GdbAdapter is already started." whenever `self._process is not
    # None`, but `terminate()` never reset it back to `None` -- so a
    # fully-terminated adapter could never be `start()`-ed again.
    processes = iter(
        (
            _BlockingFakeProcess(),
            _BlockingFakeProcess(),
        )
    )
    monkeypatch.setattr(
        gdb_adapter.subprocess,
        "Popen",
        lambda *args, **kwargs: next(processes),
    )

    adapter = GdbAdapter()
    adapter.start(
        Path("program"),
    )

    assert adapter.is_running is True

    adapter.terminate()

    assert adapter.is_running is False

    adapter.start(
        Path("program"),
    )

    assert adapter.is_running is True


def test_terminate_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = _BlockingFakeProcess()
    monkeypatch.setattr(
        gdb_adapter.subprocess,
        "Popen",
        lambda *args, **kwargs: fake_process,
    )

    adapter = GdbAdapter()
    adapter.start(
        Path("program"),
    )

    adapter.terminate()
    adapter.terminate()

    assert adapter.is_running is False
