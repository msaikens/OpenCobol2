"""Wires the Debug commands to the real debugger integration layer.

Debugging is scoped to the *active editor tab's* source file, mirroring
Build Project's existing single-file scope (there's no "main program"/
entry-point concept in the project model yet). Unlike Build Project,
a debug session genuinely requires a GnuCOBOL compiler specifically --
the whole variable-decoding pipeline depends on GnuCOBOL's generated-
header conventions -- so this resolves a GnuCOBOL toolchain directly
rather than going through the provider-agnostic
`CompilerRuntimeActivationService` abstraction Build Project uses.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import shutil

from PySide6.QtWidgets import QMessageBox, QWidget

from opencobol2.commands import CommandContext, CommandHandler
from opencobol2.compiler import CompileRequest, GnuCobolCompiler
from opencobol2.compiler.providers import GNUCOBOL_PROVIDER_ID
from opencobol2.debugger.gdb_adapter import GdbAdapterError, GdbNotRunningError
from opencobol2.debugger.models import Variable, WatchExpression
from opencobol2.debugger.service import DebuggerService, DebuggerServiceError
from opencobol2.gui.debug_session import DebugSessionController, DebugSessionError
from opencobol2.gui.editor import EditorTabsWidget, SourceEditorWidget
from opencobol2.gui.output_panel import OutputWidget
from opencobol2.gui.problems_panel import ProblemsWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.language import (
    SymbolTable,
    analyze_compilation_unit,
    parse_cobol_tokens,
    tokenize_cobol_source,
)
from opencobol2.services.compilers import CompilerProfileService
from opencobol2.services.toolchains import GnuCobolToolchainService


_COBOL_SOURCE_EXTENSIONS = (".cbl", ".cob")
_EXECUTABLE_SUFFIX = ".exe" if os.name == "nt" else ""

DEBUG_SESSION_ERRORS = (
    DebuggerServiceError,
    DebugSessionError,
    GdbAdapterError,
    GdbNotRunningError,
    TimeoutError,
)


def collect_local_variables(
    controller: DebugSessionController,
    symbol_table: SymbolTable,
) -> tuple[Variable, ...]:
    """Read every decodable top-level COBOL data item's current value.

    Condition names and RENAMES entries have no memory location of
    their own and are skipped outright; any other item `read_variable`
    can't resolve (e.g. a group item with no buffer of its own) is
    silently omitted rather than shown as an error -- its elementary
    children still appear individually, which is what a Locals panel
    should show anyway.
    """

    variables: list[Variable] = []
    seen_names: set[str] = set()

    for symbol in symbol_table.data_symbols:
        if symbol.is_condition_name or symbol.is_renames:
            continue

        normalized_name = symbol.name.upper()

        if normalized_name in seen_names:
            continue

        seen_names.add(normalized_name)

        try:
            variables.append(controller.read_variable(symbol.name))
        except DebuggerServiceError:
            continue

    return tuple(variables)


def evaluate_watch_expressions(
    controller: DebugSessionController,
    expressions: Sequence[str],
) -> tuple[WatchExpression, ...]:
    """Evaluate every watch expression: a COBOL name, else a raw GDB expression."""

    results: list[WatchExpression] = []

    for expression in expressions:
        try:
            variable = controller.read_variable(expression)
            results.append(
                WatchExpression(expression=expression, value=variable.value),
            )
            continue
        except DebuggerServiceError:
            pass

        try:
            value = controller.evaluate_expression(expression)
            results.append(WatchExpression(expression=expression, value=value))
        except DEBUG_SESSION_ERRORS as error:
            results.append(
                WatchExpression(expression=expression, error=str(error)),
            )

    return tuple(results)


def create_debug_start_handler(
    *,
    editor_tabs_widget: EditorTabsWidget,
    project_explorer: ProjectExplorerWidget,
    debug_controller: DebugSessionController,
    compiler_profile_service: CompilerProfileService,
    toolchain_service: GnuCobolToolchainService,
    symbol_table_holder: list[SymbolTable | None],
    output_widget: OutputWidget,
    problems_widget: ProblemsWidget,
    gdb_executable: str = "gdb",
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that compiles the active file with debug symbols
    and starts a real debug session against it."""

    def handle_debug_start(context: CommandContext) -> None:
        parent_widget = parent_widget_provider()

        if debug_controller.is_active:
            QMessageBox.information(
                parent_widget,
                "Start Debugging",
                "A debug session is already active.",
            )
            return

        editor = editor_tabs_widget.currentWidget()

        if not isinstance(editor, SourceEditorWidget):
            QMessageBox.information(
                parent_widget,
                "Start Debugging",
                "Open a COBOL file to debug first.",
            )
            return

        workspace_document = (
            editor_tabs_widget.document_service.workspace.get_document(
                editor.document_id,
            )
        )

        if workspace_document.document.is_modified:
            editor_tabs_widget.save_active_document()
            workspace_document = (
                editor_tabs_widget.document_service.workspace.get_document(
                    editor.document_id,
                )
            )

        source_path = workspace_document.document.path

        if (
            source_path is None
            or source_path.suffix.lower() not in _COBOL_SOURCE_EXTENSIONS
        ):
            QMessageBox.information(
                parent_widget,
                "Start Debugging",
                "The active file is not a saved .cbl/.cob source file.",
            )
            return

        if shutil.which(gdb_executable) is None:
            QMessageBox.warning(
                parent_widget,
                "Start Debugging",
                f"Unable to find the GDB executable {gdb_executable!r}.",
            )
            return

        project = project_explorer.project

        try:
            project_profile_id = (
                project.properties.default_compiler_profile_id
                if project is not None
                else None
            )
            resolution = (
                compiler_profile_service.resolve(project_profile_id)
                if project_profile_id is not None
                else compiler_profile_service.resolve_default()
            )
        except LookupError as error:
            QMessageBox.warning(parent_widget, "Start Debugging", str(error))
            return

        if resolution.profile.provider_id != GNUCOBOL_PROVIDER_ID:
            QMessageBox.warning(
                parent_widget,
                "Start Debugging",
                "Debugging requires a GnuCOBOL compiler profile as the "
                "default -- configure one in Tools > Compiler Profiles.",
            )
            return

        toolchain = toolchain_service.discover(resolution.profile)

        if toolchain is None:
            QMessageBox.warning(
                parent_widget,
                "Start Debugging",
                "Unable to discover a usable GnuCOBOL toolchain.",
            )
            return

        output_directory = (
            (project.root_path / project.properties.output_directory)
            if project is not None
            else source_path.parent
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        # cobc always ensures a native executable extension on the
        # output it actually writes -- on Windows specifically, it
        # *replaces* any other extension the requested name already
        # has with ".exe" rather than appending to it (verified: a
        # requested "demo.debug" compiles to "demo.exe", not
        # "demo.debug.exe"). Requesting the real final name directly,
        # with no other dot in it, is what makes this path prediction
        # reliable rather than guessing at cobc's renaming behavior.
        executable_path = output_directory / (
            f"{source_path.stem}_debug{_EXECUTABLE_SUFFIX}"
        )

        request = CompileRequest(
            source_path=source_path,
            output_path=executable_path,
            working_directory=output_directory,
            debug_symbols=True,
        )
        compilation = GnuCobolCompiler(toolchain=toolchain).compile(request)
        result = compilation.process_result

        if result.stdout:
            output_widget.append_line(result.stdout)

        if result.stderr:
            output_widget.append_line(result.stderr)

        problems_widget.set_diagnostics(compilation.diagnostics)

        if not compilation.succeeded:
            output_widget.append_line(
                f"Debug build failed: {source_path.name}",
            )
            QMessageBox.warning(
                parent_widget,
                "Start Debugging",
                "Compilation failed -- see Output/Problems for details.",
            )
            return

        output_widget.append_line(
            f"Debug build succeeded: {source_path.name}",
        )

        lex_result = tokenize_cobol_source(source_path.read_text())
        parse_result = parse_cobol_tokens(lex_result)
        analysis = analyze_compilation_unit(parse_result.unit)
        symbol_table_holder[0] = analysis.symbol_table

        service = DebuggerService(gdb_executable=gdb_executable)

        try:
            service.start_session(
                executable_path,
                source_path=source_path,
                symbol_table=analysis.symbol_table,
                environment=toolchain.process_environment(os.environ),
                header_paths=(
                    output_directory / f"{source_path.stem}.c.l.h",
                    output_directory / f"{source_path.stem}.c.h",
                ),
            )
            debug_controller.start(
                service,
                source_path=source_path,
                document_id=editor.document_id,
                breakpoint_lines=editor.breakpoint_lines,
            )
        except DEBUG_SESSION_ERRORS as error:
            service.stop()
            QMessageBox.warning(
                parent_widget,
                "Start Debugging",
                f"Failed to start the debug session: {error}",
            )

    return handle_debug_start


def create_debug_stop_handler(
    *,
    debug_controller: DebugSessionController,
) -> CommandHandler:
    """Create a handler that terminates the active debug session, if any."""

    def handle_debug_stop(context: CommandContext) -> None:
        if debug_controller.is_active:
            debug_controller.stop()

    return handle_debug_stop


def _create_session_action_handler(
    action_name: str,
    action: Callable[[DebugSessionController], object],
    *,
    debug_controller: DebugSessionController,
    parent_widget_provider: Callable[[], QWidget | None],
) -> CommandHandler:
    def handle_action(context: CommandContext) -> None:
        if not debug_controller.is_active:
            return

        try:
            action(debug_controller)
        except DEBUG_SESSION_ERRORS as error:
            QMessageBox.warning(
                parent_widget_provider(),
                action_name,
                str(error),
            )

    return handle_action


def create_debug_continue_handler(
    *,
    debug_controller: DebugSessionController,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that resumes a paused debug session."""

    return _create_session_action_handler(
        "Continue",
        lambda controller: controller.continue_(),
        debug_controller=debug_controller,
        parent_widget_provider=parent_widget_provider,
    )


def create_debug_step_over_handler(
    *,
    debug_controller: DebugSessionController,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that steps over one COBOL source line."""

    return _create_session_action_handler(
        "Step Over",
        lambda controller: controller.step_over(),
        debug_controller=debug_controller,
        parent_widget_provider=parent_widget_provider,
    )


def create_debug_step_into_handler(
    *,
    debug_controller: DebugSessionController,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that steps into one COBOL source line."""

    return _create_session_action_handler(
        "Step Into",
        lambda controller: controller.step_into(),
        debug_controller=debug_controller,
        parent_widget_provider=parent_widget_provider,
    )


def create_debug_step_out_handler(
    *,
    debug_controller: DebugSessionController,
    parent_widget_provider: Callable[[], QWidget | None] = lambda: None,
) -> CommandHandler:
    """Create a handler that runs until the current function returns."""

    return _create_session_action_handler(
        "Step Out",
        lambda controller: controller.step_out(),
        debug_controller=debug_controller,
        parent_widget_provider=parent_widget_provider,
    )
