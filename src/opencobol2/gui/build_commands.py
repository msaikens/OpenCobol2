"""Wires the Build Project command to the real compiler integration layer.

There is no "main program"/entry-point concept anywhere in the project
model yet, so "build" here means: find every `.cbl`/`.cob` file under the
project root (honoring `excluded_patterns`, same convention as the Project
Explorer tree) and compile each one independently as its own executable.
Multi-file program linking is not modeled.
"""

from __future__ import annotations

from collections.abc import Callable
import fnmatch
from pathlib import Path

from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from opencobol2.commands import (
    CommandContext,
    CommandHandler,
)
from opencobol2.compiler import (
    CompileRequest,
    CompilerOutputKind,
)
from opencobol2.compiler.providers import (
    CompilerProviderNotFoundError,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntimeFactoryNotFoundError,
    GnuCobolRuntimeUnavailableError,
)
from opencobol2.gui.output_panel import OutputWidget
from opencobol2.gui.problems_panel import ProblemsWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import Project
from opencobol2.services import (
    CompilerProfileNotFoundError,
    CompilerRuntimeActivationError,
    CompilerRuntimeActivationService,
    DefaultCompilerProfileNotConfiguredError,
)


_COBOL_SOURCE_EXTENSIONS = (
    ".cbl",
    ".cob",
)

_RUNTIME_ACTIVATION_ERRORS = (
    CompilerProfileNotFoundError,
    CompilerProviderNotFoundError,
    DefaultCompilerProfileNotConfiguredError,
    CompilerRuntimeActivationError,
    CompilerRuntimeFactoryNotFoundError,
    GnuCobolRuntimeUnavailableError,
)


def discover_cobol_source_files(
    project: Project,
) -> tuple[Path, ...]:
    """Recursively find COBOL source files under a project root.

    Honors `project.excluded_patterns` using the same `fnmatch`-against-name
    convention as `opencobol2.gui.project_explorer`.
    """

    found_files: list[Path] = []
    _scan_directory(
        project.root_path,
        project.excluded_patterns,
        found_files,
    )

    return tuple(
        sorted(
            found_files,
        )
    )


def _scan_directory(
    directory: Path,
    excluded_patterns: tuple[str, ...],
    found_files: list[Path],
) -> None:
    """Recursively collect COBOL source files from one directory."""

    if not directory.is_dir():
        return

    try:
        entries = sorted(
            directory.iterdir(),
            key=lambda entry: entry.name.lower(),
        )
    except OSError:
        return

    for entry in entries:
        if any(
            fnmatch.fnmatch(
                entry.name,
                pattern,
            )
            for pattern in excluded_patterns
        ):
            continue

        if entry.is_dir():
            _scan_directory(
                entry,
                excluded_patterns,
                found_files,
            )
        elif (
            entry.suffix.lower()
            in _COBOL_SOURCE_EXTENSIONS
        ):
            found_files.append(
                entry,
            )


def create_build_project_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    output_widget: OutputWidget,
    problems_widget: ProblemsWidget,
    runtime_activation_service: CompilerRuntimeActivationService,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that builds every COBOL source file in the open project.

    Uses the project's own `properties.default_compiler_profile_id` when
    set (via Project Properties); otherwise falls back to the globally
    configured default compiler profile.
    """

    def handle_build_project(
        context: CommandContext,
    ) -> None:
        parent_widget = (
            parent_widget_provider()
        )
        project = project_explorer.project

        if project is None:
            QMessageBox.information(
                parent_widget,
                "Build Project",
                "No project is open.",
            )
            return

        output_widget.clear()
        problems_widget.clear_diagnostics()

        source_files = discover_cobol_source_files(
            project,
        )

        if not source_files:
            output_widget.append_line(
                "No COBOL source files (.cbl/.cob) "
                "found in the project.",
            )
            return

        project_profile_id = (
            project.properties.default_compiler_profile_id
        )

        try:
            runtime = (
                runtime_activation_service.activate(
                    project_profile_id,
                )
                if project_profile_id is not None
                else runtime_activation_service.activate_default()
            )
        except _RUNTIME_ACTIVATION_ERRORS as error:
            output_widget.append_line(
                f"Build failed: {error}",
            )
            return

        output_directory = (
            project.root_path
            / project.properties.output_directory
        )
        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        all_diagnostics = []

        for source_file in source_files:
            relative_path = source_file.relative_to(
                project.root_path,
            )
            output_widget.append_line(
                f"Compiling {relative_path}...",
            )

            request = CompileRequest(
                source_path=source_file,
                output_path=(
                    output_directory
                    / source_file.stem
                ),
                output_kind=(
                    CompilerOutputKind.EXECUTABLE
                ),
                working_directory=(
                    project.root_path
                ),
            )

            compilation = runtime.compile(
                request,
            )

            if compilation.process_result.stdout:
                output_widget.append_line(
                    compilation.process_result.stdout,
                )

            if compilation.process_result.stderr:
                output_widget.append_line(
                    compilation.process_result.stderr,
                )

            status_word = (
                "succeeded"
                if compilation.succeeded
                else "FAILED"
            )
            output_widget.append_line(
                f"{relative_path}: {status_word}",
            )

            all_diagnostics.extend(
                compilation.diagnostics,
            )

        output_widget.append_line(
            f"Build complete: {len(source_files)} "
            "file(s) compiled.",
        )
        problems_widget.set_diagnostics(
            tuple(
                all_diagnostics,
            ),
        )

    return handle_build_project
