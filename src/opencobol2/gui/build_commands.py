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
import shutil

from PySide6.QtWidgets import (
    QMessageBox,
    QWidget,
)

from opencobol2.commands import (
    CommandContext,
    CommandHandler,
)
from opencobol2.compiler import (
    EXECUTABLE_SUFFIX,
    CompileRequest,
    CompilerOutputKind,
    GnuCobolCompiler,
)
from opencobol2.compiler.providers import (
    GNUCOBOL_PROVIDER_ID,
    CompilerProviderNotFoundError,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntimeFactoryNotFoundError,
    GnuCobolRuntimeUnavailableError,
)
from opencobol2.gui.editor import EditorTabsWidget, SourceEditorWidget
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
from opencobol2.services.compilers import CompilerProfileService
from opencobol2.services.toolchains import GnuCobolToolchainService


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


def _is_up_to_date(
    source_file: Path,
    output_path: Path,
) -> bool:
    """Return whether a compiled output is at least as new as its source.

    Build Project skips recompiling in this case. A skipped file's
    diagnostics from its last actual compile are deliberately not
    carried forward -- Problems reflects only what this run actually
    compiled, not a persisted, potentially-stale cache. Rebuild
    Project (clean, then build) is the existing escape hatch: an
    emptied output directory means nothing is ever "up to date", so
    every file gets a full recompile with fresh diagnostics.
    """

    if not output_path.exists():
        return False

    return (
        output_path.stat().st_mtime
        >= source_file.stat().st_mtime
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
        compiled_count = 0
        skipped_count = 0

        for source_file in source_files:
            relative_path = source_file.relative_to(
                project.root_path,
            )

            # Editor §CompilerProcess-1: deriving the output path from
            # the source filename alone (discarding its directory)
            # meant two source files with the same base name in
            # different folders silently clobbered each other's
            # compiled binary. Mirroring the source file's own
            # directory structure under `output_directory` keeps every
            # compiled output unique, exactly as it already is on disk
            # for the sources themselves.
            #
            # The requested name carries the real EXECUTABLE_SUFFIX up
            # front rather than relying on cobc's own extension
            # handling: on Windows, cobc always forces `-x` output to
            # end in ".exe", replacing any other extension the
            # requested name has rather than appending to it, so a
            # bare, suffix-less request would silently point the
            # up-to-date check below at a file cobc never actually
            # writes.
            output_path = (
                output_directory
                / relative_path.with_suffix(EXECUTABLE_SUFFIX)
            )

            if _is_up_to_date(source_file, output_path):
                output_widget.append_line(
                    f"{relative_path}: up to date, skipping",
                )
                skipped_count += 1
                continue

            output_widget.append_line(
                f"Compiling {relative_path}...",
            )
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            request = CompileRequest(
                source_path=source_file,
                output_path=output_path,
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
            compiled_count += 1

        output_widget.append_line(
            f"Build complete: {compiled_count} file(s) compiled, "
            f"{skipped_count} up to date.",
        )
        problems_widget.set_diagnostics(
            tuple(
                all_diagnostics,
            ),
        )

    return handle_build_project


def create_clean_project_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    output_widget: OutputWidget,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that empties the open project's output directory."""

    def handle_clean_project(
        context: CommandContext,
    ) -> None:
        parent_widget = (
            parent_widget_provider()
        )
        project = project_explorer.project

        if project is None:
            QMessageBox.information(
                parent_widget,
                "Clean Project",
                "No project is open.",
            )
            return

        output_directory = (
            project.root_path
            / project.properties.output_directory
        )

        if not output_directory.is_dir():
            output_widget.append_line(
                "Nothing to clean: the output directory "
                "does not exist.",
            )
            return

        removed_count = 0

        for entry in output_directory.iterdir():
            if entry.is_dir():
                shutil.rmtree(
                    entry,
                    ignore_errors=True,
                )
            else:
                entry.unlink(
                    missing_ok=True,
                )

            removed_count += 1

        output_widget.append_line(
            f"Clean complete: removed {removed_count} "
            f"item(s) from {project.properties.output_directory}.",
        )

    return handle_clean_project


def create_rebuild_project_handler(
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
    """Create a handler that cleans the output directory, then builds the project."""

    clean_handler = create_clean_project_handler(
        project_explorer=project_explorer,
        output_widget=output_widget,
        parent_widget_provider=parent_widget_provider,
    )
    build_handler = create_build_project_handler(
        project_explorer=project_explorer,
        output_widget=output_widget,
        problems_widget=problems_widget,
        runtime_activation_service=runtime_activation_service,
        parent_widget_provider=parent_widget_provider,
    )

    def handle_rebuild_project(
        context: CommandContext,
    ) -> None:
        clean_handler(
            context,
        )
        build_handler(
            context,
        )

    return handle_rebuild_project


def create_view_listing_handler(
    *,
    editor_tabs_widget: EditorTabsWidget,
    project_explorer: ProjectExplorerWidget,
    compiler_profile_service: CompilerProfileService,
    toolchain_service: GnuCobolToolchainService,
    output_widget: OutputWidget,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that compiles the active file with a GnuCOBOL
    program listing and opens the resulting `.lst` file.

    Listing generation (`-t`) is a GnuCOBOL `cobc`-specific flag, not
    modeled by the provider-agnostic `CompilerRuntimeActivationService`
    abstraction Build Project otherwise uses, so this resolves a
    GnuCOBOL toolchain directly and scopes to the active editor tab --
    the same boundary `debug_commands.create_debug_start_handler`
    already draws, for the same reason.
    """

    def handle_view_listing(
        context: CommandContext,
    ) -> None:
        parent_widget = (
            parent_widget_provider()
        )
        editor = editor_tabs_widget.currentWidget()

        if not isinstance(editor, SourceEditorWidget):
            QMessageBox.information(
                parent_widget,
                "View Listing File",
                "Open a COBOL file first.",
            )
            return

        workspace_document = (
            editor_tabs_widget.document_service.workspace.get_document(
                editor.document_id,
            )
        )
        source_path = workspace_document.document.path

        if (
            source_path is None
            or source_path.suffix.lower()
            not in _COBOL_SOURCE_EXTENSIONS
        ):
            QMessageBox.information(
                parent_widget,
                "View Listing File",
                "The active file is not a saved .cbl/.cob source file.",
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
                compiler_profile_service.resolve(
                    project_profile_id,
                )
                if project_profile_id is not None
                else compiler_profile_service.resolve_default()
            )
        except LookupError as error:
            QMessageBox.warning(
                parent_widget,
                "View Listing File",
                str(error),
            )
            return

        if resolution.profile.provider_id != GNUCOBOL_PROVIDER_ID:
            QMessageBox.warning(
                parent_widget,
                "View Listing File",
                "Listing generation requires a GnuCOBOL compiler "
                "profile as the default -- configure one in Tools > "
                "Compiler Profiles.",
            )
            return

        toolchain = toolchain_service.discover(
            resolution.profile,
        )

        if toolchain is None:
            QMessageBox.warning(
                parent_widget,
                "View Listing File",
                "Unable to discover a usable GnuCOBOL toolchain.",
            )
            return

        output_directory = (
            (
                project.root_path
                / project.properties.output_directory
            )
            if project is not None
            else source_path.parent
        )
        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        listing_path = (
            output_directory / f"{source_path.stem}.lst"
        )
        object_path = output_directory / (
            f"{source_path.stem}{EXECUTABLE_SUFFIX}"
        )

        request = CompileRequest(
            source_path=source_path,
            output_path=object_path,
            working_directory=output_directory,
            listing_path=listing_path,
        )
        compilation = GnuCobolCompiler(
            toolchain=toolchain,
        ).compile(
            request,
        )
        result = compilation.process_result

        if result.stdout:
            output_widget.append_line(
                result.stdout,
            )

        if result.stderr:
            output_widget.append_line(
                result.stderr,
            )

        if not listing_path.is_file():
            QMessageBox.warning(
                parent_widget,
                "View Listing File",
                "The compiler did not produce a listing file.",
            )
            return

        editor_tabs_widget.open_path(
            listing_path,
        )

    return handle_view_listing
