"""A first-cut Terminal panel: run one shell command at a time.

Real interactive PTY-based terminal emulation (a live, streaming shell
process attached to a pseudo-terminal) needs platform-specific plumbing --
ConPTY on Windows, a real pty on POSIX -- that's out of scope for this first
cut. Instead, each typed command runs to completion through a real,
synchronous `subprocess.run(shell=True)` call before its output appends to
the log, mirroring the same blocking-subprocess pattern the compiler
integration layer already uses for Build Project. `shell=True` is
intentional here, not a command-injection risk: this widget's only input
source is the user directly typing a command into their own IDE's terminal,
which is exactly what a terminal is for.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


_COMMAND_TIMEOUT_SECONDS = 60


class TerminalWidget(QWidget):
    """A command-input box over a read-only output log.

    Runs one command at a time; there is no concept of a persistent shell
    session (each command starts a fresh process), no live/streaming output
    for long-running commands, and no interactive input (`read`/prompts
    hang until the timeout).
    """

    def __init__(
        self,
        *,
        working_directory: Path | None = None,
        command_timeout_seconds: float = (
            _COMMAND_TIMEOUT_SECONDS
        ),
        parent: QWidget | None = None,
    ) -> None:
        """Build an empty terminal panel rooted at a working directory.

        Editor §ProjectPanels-6: the timeout was previously a hardcoded
        module constant with no override anywhere in the codebase.
        """

        super().__init__(
            parent,
        )

        self._working_directory = (
            working_directory
            if working_directory is not None
            else Path.cwd()
        )
        self._command_timeout_seconds = (
            command_timeout_seconds
        )

        layout = QVBoxLayout(
            self,
        )
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._output_log = QPlainTextEdit()
        self._output_log.setReadOnly(
            True,
        )
        self._output_log.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.NoWrap,
        )
        monospace_font = (
            QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont,
            )
        )
        self._output_log.setFont(
            monospace_font,
        )
        layout.addWidget(
            self._output_log,
        )

        self._command_edit = QLineEdit()
        self._command_edit.setPlaceholderText(
            "Type a command and press Enter...",
        )
        self._command_edit.returnPressed.connect(
            self._handle_return_pressed,
        )
        layout.addWidget(
            self._command_edit,
        )

    @property
    def working_directory(
        self,
    ) -> Path:
        """Return the directory commands run in."""

        return self._working_directory

    def set_working_directory(
        self,
        path: Path | None,
    ) -> None:
        """Change the directory subsequent commands run in."""

        self._working_directory = (
            path
            if path is not None
            else Path.cwd()
        )

    def append_line(
        self,
        text: str,
    ) -> None:
        """Append one line of text to the output log."""

        self._output_log.appendPlainText(
            text,
        )

    def clear_output(
        self,
    ) -> None:
        """Remove every line from the output log."""

        self._output_log.clear()

    def run_command(
        self,
        command_text: str,
    ) -> None:
        """Run one shell command to completion and log its output."""

        command_text = command_text.strip()

        if not command_text:
            return

        self.append_line(
            f"$ {command_text}",
        )

        try:
            completed_process = subprocess.run(
                command_text,
                shell=True,
                cwd=self._working_directory,
                capture_output=True,
                text=True,
                timeout=self._command_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            self.append_line(
                "error: command timed out after "
                f"{self._command_timeout_seconds}s",
            )
            return
        except OSError as error:
            self.append_line(
                f"error: {error}",
            )
            return

        if completed_process.stdout:
            self.append_line(
                completed_process.stdout.rstrip(
                    "\n",
                )
            )

        if completed_process.stderr:
            self.append_line(
                completed_process.stderr.rstrip(
                    "\n",
                )
            )

        self.append_line(
            "(exited with code "
            f"{completed_process.returncode})",
        )

    def _handle_return_pressed(
        self,
    ) -> None:
        command_text = self._command_edit.text()
        self._command_edit.clear()
        self.run_command(
            command_text,
        )
