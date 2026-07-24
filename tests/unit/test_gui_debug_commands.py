"""Unit tests for the pure debug-session helpers and simple action handlers.

`create_debug_start_handler`'s full happy path (real compile + real GDB
session) is covered by a real end-to-end GUI test instead -- see
`tests/unit/test_gui_application.py` -- since it has too many real
collaborators (a real compiler, a real toolchain, a real GDB process)
to meaningfully fake. This module covers what's left: the pure
locals/watch evaluation helpers, and the simple stop/continue/step
handlers' active/inactive/error-reporting behavior.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PySide6.QtWidgets import QMessageBox

from opencobol2.commands import CommandContext
from opencobol2.debugger.models import Breakpoint, Variable, WatchExpression
from opencobol2.debugger.service import DebuggerServiceError
from opencobol2.gui.debug_commands import (
    collect_local_variables,
    create_debug_continue_handler,
    create_debug_step_into_handler,
    create_debug_step_out_handler,
    create_debug_step_over_handler,
    create_debug_stop_handler,
    evaluate_watch_expressions,
)
from opencobol2.gui.debug_session import DebugSessionController
from opencobol2.language import (
    analyze_compilation_unit,
    parse_cobol_tokens,
    tokenize_cobol_source,
)


class _FakeDebuggerService:
    """Records calls in place of a real `DebuggerService`."""

    def __init__(self) -> None:
        self.stop_called = False
        self.continue_called = False
        self.step_out_called = False
        self.raise_on_step_over: Exception | None = None
        self.raise_on_step_into: Exception | None = None
        self.variables: dict[str, str] = {}
        self.expressions: dict[str, str] = {}

    def on_stopped(self, callback) -> None:
        pass

    def run(self) -> None:
        pass

    def stop(self) -> None:
        self.stop_called = True

    def continue_(self) -> None:
        self.continue_called = True

    def step_over_cobol_line(self):
        if self.raise_on_step_over is not None:
            raise self.raise_on_step_over

        return "stepped-over"

    def step_into_cobol_line(self):
        if self.raise_on_step_into is not None:
            raise self.raise_on_step_into

        return "stepped-into"

    def step_out(self) -> None:
        self.step_out_called = True

    def add_breakpoint(self, source_file: str, line: int) -> Breakpoint:
        return Breakpoint(number=1, source_path=Path(source_file), line=line)

    def remove_breakpoint(self, number: int) -> None:
        pass

    def breakpoints(self) -> tuple[Breakpoint, ...]:
        return ()

    def read_variable(self, name: str) -> Variable:
        if name not in self.variables:
            raise DebuggerServiceError(f"{name!r} is not a known data item.")

        return Variable(name=name, value=self.variables[name])

    def evaluate_expression(self, expression: str) -> str:
        if expression not in self.expressions:
            raise DebuggerServiceError(
                f"Unable to evaluate expression: {expression!r}.",
            )

        return self.expressions[expression]


def _started_controller(service: _FakeDebuggerService) -> DebugSessionController:
    controller = DebugSessionController()
    controller.start(
        service,
        source_path=Path("demo.cbl"),
        document_id=uuid4(),
    )
    return controller


# -- collect_local_variables --------------------------------------------


_PROGRAM = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-A  PIC 9(4) VALUE 10.\n"
    "       01  WS-B  PIC 9(4) VALUE 20.\n"
    "           88  WS-B-IS-ZERO VALUE 0.\n"
    "       PROCEDURE DIVISION.\n"
    "       STOP RUN.\n"
)


def _symbol_table():
    lex_result = tokenize_cobol_source(_PROGRAM)
    parse_result = parse_cobol_tokens(lex_result)
    analysis = analyze_compilation_unit(parse_result.unit)
    return analysis.symbol_table


def test_collect_local_variables_reads_every_decodable_item(qapp) -> None:
    service = _FakeDebuggerService()
    service.variables = {"WS-A": "0010", "WS-B": "0020"}
    controller = _started_controller(service)

    variables = collect_local_variables(controller, _symbol_table())

    assert {variable.name: variable.value for variable in variables} == {
        "WS-A": "0010",
        "WS-B": "0020",
    }


def test_collect_local_variables_skips_condition_names(qapp) -> None:
    service = _FakeDebuggerService()
    service.variables = {"WS-A": "0010", "WS-B": "0020"}
    controller = _started_controller(service)

    variables = collect_local_variables(controller, _symbol_table())

    assert "WS-B-IS-ZERO" not in {variable.name for variable in variables}


def test_collect_local_variables_omits_items_with_no_known_location(
    qapp,
) -> None:
    service = _FakeDebuggerService()
    service.variables = {"WS-A": "0010"}
    controller = _started_controller(service)

    variables = collect_local_variables(controller, _symbol_table())

    assert {variable.name for variable in variables} == {"WS-A"}


# -- evaluate_watch_expressions ------------------------------------------


def test_evaluate_watch_expressions_prefers_a_cobol_variable_read(
    qapp,
) -> None:
    service = _FakeDebuggerService()
    service.variables = {"WS-SUM": "0030"}
    controller = _started_controller(service)

    watches = evaluate_watch_expressions(controller, ("WS-SUM",))

    assert watches == (
        WatchExpression(expression="WS-SUM", value="0030"),
    )


def test_evaluate_watch_expressions_falls_back_to_raw_expression(
    qapp,
) -> None:
    service = _FakeDebuggerService()
    service.expressions = {"1 + 1": "2"}
    controller = _started_controller(service)

    watches = evaluate_watch_expressions(controller, ("1 + 1",))

    assert watches == (
        WatchExpression(expression="1 + 1", value="2"),
    )


def test_evaluate_watch_expressions_reports_an_error(qapp) -> None:
    controller = _started_controller(_FakeDebuggerService())

    watches = evaluate_watch_expressions(controller, ("bogus",))

    assert len(watches) == 1
    assert watches[0].expression == "bogus"
    assert watches[0].value is None
    assert watches[0].error is not None


# -- simple action handlers -----------------------------------------------


def test_stop_handler_stops_only_when_active(qapp) -> None:
    service = _FakeDebuggerService()
    controller = _started_controller(service)
    handler = create_debug_stop_handler(debug_controller=controller)

    handler(CommandContext())

    assert service.stop_called is True
    assert controller.is_active is False


def test_stop_handler_is_a_no_op_when_inactive(qapp) -> None:
    controller = DebugSessionController()
    handler = create_debug_stop_handler(debug_controller=controller)

    handler(CommandContext())  # must not raise


def test_continue_handler_is_a_no_op_when_inactive(qapp) -> None:
    controller = DebugSessionController()
    handler = create_debug_continue_handler(debug_controller=controller)

    handler(CommandContext())  # must not raise


def test_continue_handler_continues_when_active(qapp) -> None:
    service = _FakeDebuggerService()
    controller = _started_controller(service)
    handler = create_debug_continue_handler(debug_controller=controller)

    handler(CommandContext())

    assert service.continue_called is True


def test_step_over_handler_steps_when_active(qapp) -> None:
    service = _FakeDebuggerService()
    controller = _started_controller(service)
    handler = create_debug_step_over_handler(debug_controller=controller)

    handler(CommandContext())  # must not raise


def test_step_into_handler_steps_when_active(qapp) -> None:
    service = _FakeDebuggerService()
    controller = _started_controller(service)
    handler = create_debug_step_into_handler(debug_controller=controller)

    handler(CommandContext())  # must not raise


def test_step_out_handler_steps_when_active(qapp) -> None:
    service = _FakeDebuggerService()
    controller = _started_controller(service)
    handler = create_debug_step_out_handler(debug_controller=controller)

    handler(CommandContext())

    assert service.step_out_called is True


def test_step_over_handler_reports_an_error_via_message_box(qapp) -> None:
    service = _FakeDebuggerService()
    service.raise_on_step_over = DebuggerServiceError("boom")
    controller = _started_controller(service)
    handler = create_debug_step_over_handler(debug_controller=controller)

    with patch.object(QMessageBox, "warning") as mock_warning:
        handler(CommandContext())

    mock_warning.assert_called_once()
