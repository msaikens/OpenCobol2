"""Wires Edit > Find in Files to a real cross-file COBOL source search."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QInputDialog,
    QMessageBox,
    QWidget,
)

from opencobol2.commands import CommandContext, CommandHandler
from opencobol2.gui.build_commands import discover_cobol_source_files
from opencobol2.gui.find_results_panel import (
    FindResult,
    FindResultsWidget,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import Project


def search_project_for_text(
    project: Project,
    query: str,
) -> tuple[FindResult, ...]:
    """Case-insensitively find every source line containing `query`.

    Searches every `.cbl`/`.cob` file under the project root (the same
    discovery `discover_cobol_source_files` uses for Build Project),
    reading each file independently so one unreadable file doesn't abort
    the whole search.
    """

    if not query:
        return ()

    lowered_query = query.lower()
    results: list[FindResult] = []

    for path in discover_cobol_source_files(
        project,
    ):
        try:
            text = path.read_text(
                errors="replace",
            )
        except OSError:
            continue

        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            lowered_line = line.lower()
            search_start = 0

            while True:
                match_index = lowered_line.find(
                    lowered_query,
                    search_start,
                )

                if match_index < 0:
                    break

                results.append(
                    FindResult(
                        path=path,
                        line=line_number,
                        column=match_index + 1,
                        line_text=line.strip(),
                    )
                )
                search_start = match_index + len(
                    lowered_query,
                )

    return tuple(
        results,
    )


def create_find_in_files_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    find_results_widget: FindResultsWidget,
    reveal_find_results: Callable[
        [],
        None,
    ] = lambda: None,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that prompts for a query and searches project files."""

    def handle_find_in_files(
        context: CommandContext,
    ) -> tuple[FindResult, ...] | None:
        parent_widget = (
            parent_widget_provider()
        )
        project = project_explorer.project

        if project is None:
            QMessageBox.information(
                parent_widget,
                "Find in Files",
                "Open a project before searching its files.",
            )
            return None

        query, ok = QInputDialog.getText(
            parent_widget,
            "Find in Files",
            "Search for:",
        )

        if not ok or not query.strip():
            return None

        results = search_project_for_text(
            project,
            query,
        )
        find_results_widget.set_results(
            results,
        )
        reveal_find_results()

        return results

    return handle_find_in_files
