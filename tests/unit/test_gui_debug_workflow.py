"""Real end-to-end test of the Debug menu against a live GDB session.

Goes through the actual application bootstrap (`create_main_window`),
the actual Debug menu actions, a real `cobc` debug-symbol compile, and
a real `gdb` session -- not mocks. Skips cleanly if GnuCOBOL or gdb
isn't installed. `DebuggerService` itself is already exhaustively
proven for real in `tests/integration/test_debugger_service_session.py`;
this test instead proves the GUI wiring around it: Start/Stop
Debugging, breakpoint sync from the editor, and the Call Stack/Locals/
Watch panels actually populate from a live session.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from opencobol2.gui.application import create_main_window
from opencobol2.project import create_project
from opencobol2.settings import SettingsService, SettingsStorage
from opencobol2.toolchains import discover_gnucobol


_SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DEMO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-A PIC 9(4) VALUE 10.
       01 WS-B PIC 9(4) VALUE 20.
       01 WS-SUM PIC 9(4).
       PROCEDURE DIVISION.
       MAIN-PARA.
           ADD WS-A TO WS-B GIVING WS-SUM.
           DISPLAY "SUM=" WS-SUM.
           STOP RUN.
"""


def _find_action(menu, title: str):
    actions = menu.actions()

    for action in actions:
        if action.text() == title:
            return action

    raise ValueError(f"No action titled {title!r} found.")


def _wait_until(condition, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        QApplication.processEvents()

        if condition():
            return True

        time.sleep(0.01)

    return False


def _fail_on_message_box(*args, **_kwargs) -> None:
    # QMessageBox.warning()/.information() are static methods, so
    # (unlike QMenu.exec(), which can't be reliably patched) mocking
    # them here is reliable -- but leaving either unmocked on a golden
    # path that unexpectedly hits one would call the real, unmockable
    # QMessageBox.exec() underneath and hang the whole test forever
    # under the offscreen platform, with nothing there to dismiss it.
    # Fail loudly and immediately instead.
    title, text = args[1], args[2]
    raise AssertionError(f"Unexpected message box {title!r}: {text!r}")


def test_debug_menu_drives_a_real_session_end_to_end(
    qapp,
    tmp_path: Path,
) -> None:
    toolchain = discover_gnucobol()
    gdb_path = shutil.which("gdb")

    if toolchain is None or gdb_path is None:
        pytest.skip(
            "GnuCOBOL and/or gdb are not installed; skipping "
            "real Debug menu integration test."
        )

    source_path = tmp_path / "demo.cbl"
    source_path.write_text(_SOURCE)
    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    project = create_project(name="Demo", root_path=tmp_path)

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    editor_tabs = window.centralWidget()
    editor_tabs.open_path(source_path)
    editor = editor_tabs.widget(0)
    editor.go_to_line(10)
    editor.toggle_breakpoint_at_cursor()

    call_stack_widget = window.dock_manager.get_dock_widget(
        "call-stack",
    ).widget()
    locals_widget = window.dock_manager.get_dock_widget(
        "locals",
    ).widget()
    watch_widget = window.dock_manager.get_dock_widget(
        "watch",
    ).widget()
    output_widget = window.dock_manager.get_dock_widget(
        "output",
    ).widget()

    debug_menu = window.menus["debug"]

    try:
        with (
            patch.object(QMessageBox, "warning", _fail_on_message_box),
            patch.object(
                QMessageBox, "information", _fail_on_message_box,
            ),
        ):
            debug_menu.aboutToShow.emit()
            _find_action(debug_menu, "Start Debugging").trigger()

            assert _wait_until(
                lambda: call_stack_widget.rowCount() > 0,
            ), (
                "Call Stack never populated after Start Debugging. "
                f"Output so far:\n{output_widget.toPlainText()}"
            )
            assert call_stack_widget.item(0, 3).text() == "10"

            locals_by_name = {
                locals_widget.item(row, 0).text(): (
                    locals_widget.item(row, 1).text()
                )
                for row in range(locals_widget.rowCount())
            }
            assert locals_by_name["WS-A"] == "0010"
            assert locals_by_name["WS-SUM"] == "0000"

            # A COBOL name evaluates immediately from the paused state.
            watch_widget._input.setText("WS-B")
            watch_widget._handle_add()
            assert _wait_until(
                lambda: watch_widget._table.rowCount() == 1
                and watch_widget._table.item(0, 1).text() == "0020",
            )

            # Adding a breakpoint from the editor mid-session syncs to
            # a real GDB breakpoint: continuing should stop again at
            # line 11 (right after the ADD executes) rather than
            # running straight to completion.
            editor.go_to_line(11)
            editor.toggle_breakpoint_at_cursor()

            debug_menu.aboutToShow.emit()
            _find_action(debug_menu, "Continue").trigger()

            assert _wait_until(
                lambda: call_stack_widget.rowCount() > 0
                and call_stack_widget.item(0, 3).text() == "11",
            ), "The breakpoint added mid-session was never synced to GDB."

            locals_by_name = {
                locals_widget.item(row, 0).text(): (
                    locals_widget.item(row, 1).text()
                )
                for row in range(locals_widget.rowCount())
            }
            assert locals_by_name["WS-SUM"] == "0030"

            # -- run to completion --
            debug_menu.aboutToShow.emit()
            _find_action(debug_menu, "Continue").trigger()

            assert _wait_until(
                lambda: (
                    "Debug session ended" in output_widget.toPlainText()
                ),
            ), (
                "Debug session never ended after Continue. "
                f"Output so far:\n{output_widget.toPlainText()}"
            )
            assert call_stack_widget.rowCount() == 0
            assert locals_widget.rowCount() == 0
    finally:
        debug_menu.aboutToShow.emit()
        _find_action(debug_menu, "Stop Debugging").trigger()


def test_stop_debugging_while_paused_clears_every_debug_panel(
    qapp,
    tmp_path: Path,
) -> None:
    # Editor §DebugGUI-1/2: ending a session any way other than a
    # natural program exit -- i.e. clicking "Stop Debugging" while
    # still paused at a breakpoint -- used to leave every debug panel
    # showing the just-ended session's stale data indefinitely, with
    # the Memory panel specifically never clearing under any
    # circumstance at all, including the one path (natural exit) that
    # already cleared the other five.
    toolchain = discover_gnucobol()
    gdb_path = shutil.which("gdb")

    if toolchain is None or gdb_path is None:
        pytest.skip(
            "GnuCOBOL and/or gdb are not installed; skipping "
            "real Debug menu integration test."
        )

    source_path = tmp_path / "demo.cbl"
    source_path.write_text(_SOURCE)
    settings_service = SettingsService(
        SettingsStorage(tmp_path / "settings.json"),
    )
    project = create_project(name="Demo", root_path=tmp_path)

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    editor_tabs = window.centralWidget()
    editor_tabs.open_path(source_path)
    editor = editor_tabs.widget(0)
    editor.go_to_line(10)
    editor.toggle_breakpoint_at_cursor()

    call_stack_widget = window.dock_manager.get_dock_widget(
        "call-stack",
    ).widget()
    locals_widget = window.dock_manager.get_dock_widget(
        "locals",
    ).widget()
    threads_widget = window.dock_manager.get_dock_widget(
        "threads",
    ).widget()
    registers_widget = window.dock_manager.get_dock_widget(
        "registers",
    ).widget()
    watch_widget = window.dock_manager.get_dock_widget(
        "watch",
    ).widget()
    memory_widget = window.dock_manager.get_dock_widget(
        "memory",
    ).widget()
    output_widget = window.dock_manager.get_dock_widget(
        "output",
    ).widget()

    debug_menu = window.menus["debug"]

    with (
        patch.object(QMessageBox, "warning", _fail_on_message_box),
        patch.object(
            QMessageBox, "information", _fail_on_message_box,
        ),
    ):
        debug_menu.aboutToShow.emit()
        _find_action(debug_menu, "Start Debugging").trigger()

        assert _wait_until(
            lambda: call_stack_widget.rowCount() > 0,
        ), (
            "Call Stack never populated after Start Debugging. "
            f"Output so far:\n{output_widget.toPlainText()}"
        )

        watch_widget._input.setText("WS-B")
        watch_widget._handle_add()
        assert _wait_until(
            lambda: watch_widget._table.rowCount() == 1
            and watch_widget._table.item(0, 1).text() == "0020",
        )

        memory_widget._address_input.setText("&main")
        memory_widget._handle_read()
        assert memory_widget._output.toPlainText() != ""

        # Every panel has real, non-empty data from the live,
        # still-paused session before Stop Debugging runs.
        assert call_stack_widget.rowCount() > 0
        assert locals_widget.rowCount() > 0
        assert threads_widget.rowCount() > 0
        assert registers_widget.rowCount() > 0
        assert watch_widget._table.rowCount() > 0

        debug_menu.aboutToShow.emit()
        _find_action(debug_menu, "Stop Debugging").trigger()

        assert call_stack_widget.rowCount() == 0
        assert locals_widget.rowCount() == 0
        assert threads_widget.rowCount() == 0
        assert registers_widget.rowCount() == 0
        # `clear_watches()` deliberately keeps the expression row (so
        # the user doesn't have to retype it next session) and only
        # blanks its value -- unlike the other panels, which remove
        # every row outright.
        assert watch_widget._table.item(0, 1).text() == ""
        assert memory_widget._output.toPlainText() == ""
