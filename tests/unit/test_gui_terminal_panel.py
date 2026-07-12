"""Unit tests for the first-cut Terminal panel, against real subprocesses."""

from __future__ import annotations

from pathlib import Path
import sys

from opencobol2.gui.terminal_panel import TerminalWidget


def _write_script(
    tmp_path: Path,
    body: str,
) -> Path:
    script_path = tmp_path / "script.py"
    script_path.write_text(
        body,
    )

    return script_path


def _run_script(
    terminal: TerminalWidget,
    script_path: Path,
    *args: str,
) -> None:
    quoted_args = " ".join(
        f'"{arg}"'
        for arg in (
            sys.executable,
            str(
                script_path,
            ),
            *args,
        )
    )
    terminal.run_command(
        quoted_args,
    )


def test_run_command_with_empty_text_does_nothing(
    qapp,
) -> None:
    terminal = TerminalWidget()

    terminal.run_command(
        "   ",
    )

    assert terminal._output_log.toPlainText() == ""


def test_run_command_executes_and_logs_stdout_and_exit_code(
    qapp,
    tmp_path: Path,
) -> None:
    terminal = TerminalWidget()
    script_path = _write_script(
        tmp_path,
        "print('hello from script')\n",
    )

    _run_script(
        terminal,
        script_path,
    )

    log_text = terminal._output_log.toPlainText()
    assert "hello from script" in log_text
    assert "(exited with code 0)" in log_text


def test_run_command_logs_a_nonzero_exit_code(
    qapp,
    tmp_path: Path,
) -> None:
    terminal = TerminalWidget()
    script_path = _write_script(
        tmp_path,
        "import sys\nsys.exit(3)\n",
    )

    _run_script(
        terminal,
        script_path,
    )

    assert (
        "(exited with code 3)"
        in terminal._output_log.toPlainText()
    )


def test_run_command_logs_stderr(
    qapp,
    tmp_path: Path,
) -> None:
    terminal = TerminalWidget()
    script_path = _write_script(
        tmp_path,
        "import sys\nprint('uh oh', file=sys.stderr)\n",
    )

    _run_script(
        terminal,
        script_path,
    )

    assert (
        "uh oh"
        in terminal._output_log.toPlainText()
    )


def test_run_command_uses_the_configured_working_directory(
    qapp,
    tmp_path: Path,
) -> None:
    script_path = _write_script(
        tmp_path,
        "import pathlib\nprint(pathlib.Path.cwd())\n",
    )
    working_directory = tmp_path / "workdir"
    working_directory.mkdir()
    terminal = TerminalWidget(
        working_directory=working_directory,
    )

    _run_script(
        terminal,
        script_path,
    )

    assert (
        str(
            working_directory,
        )
        in terminal._output_log.toPlainText()
    )


def test_set_working_directory_updates_subsequent_commands(
    qapp,
    tmp_path: Path,
) -> None:
    script_path = _write_script(
        tmp_path,
        "import pathlib\nprint(pathlib.Path.cwd())\n",
    )
    new_directory = tmp_path / "elsewhere"
    new_directory.mkdir()
    terminal = TerminalWidget()

    terminal.set_working_directory(
        new_directory,
    )
    _run_script(
        terminal,
        script_path,
    )

    assert terminal.working_directory == new_directory
    assert (
        str(
            new_directory,
        )
        in terminal._output_log.toPlainText()
    )


def test_set_working_directory_with_none_falls_back_to_cwd(
    qapp,
    tmp_path: Path,
) -> None:
    terminal = TerminalWidget(
        working_directory=tmp_path,
    )

    terminal.set_working_directory(
        None,
    )

    assert terminal.working_directory == Path.cwd()


def test_return_pressed_runs_the_typed_command_and_clears_the_input(
    qapp,
    tmp_path: Path,
) -> None:
    terminal = TerminalWidget()
    script_path = _write_script(
        tmp_path,
        "print('typed and run')\n",
    )
    command_text = " ".join(
        f'"{part}"'
        for part in (
            sys.executable,
            str(
                script_path,
            ),
        )
    )
    terminal._command_edit.setText(
        command_text,
    )

    terminal._handle_return_pressed()

    assert terminal._command_edit.text() == ""
    assert (
        "typed and run"
        in terminal._output_log.toPlainText()
    )


def test_append_line_and_clear_output(
    qapp,
) -> None:
    terminal = TerminalWidget()

    terminal.append_line(
        "hello",
    )
    assert (
        "hello"
        in terminal._output_log.toPlainText()
    )

    terminal.clear_output()

    assert terminal._output_log.toPlainText() == ""
