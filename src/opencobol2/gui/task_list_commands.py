"""Scans every project source file for TODO/FIXME-style task markers."""

from __future__ import annotations

from opencobol2.gui.build_commands import discover_cobol_source_files
from opencobol2.gui.task_list_panel import ProjectTaskEntry
from opencobol2.language import compute_task_list_entries
from opencobol2.project import Project


def scan_project_for_tasks(
    project: Project,
) -> tuple[ProjectTaskEntry, ...]:
    """Find every task-tagged comment across a project's COBOL source files.

    Reads each discovered file independently so one unreadable file
    doesn't abort the whole scan, mirroring
    `opencobol2.gui.search_commands.search_project_for_text`.
    """

    entries: list[ProjectTaskEntry] = []

    for path in discover_cobol_source_files(
        project,
    ):
        try:
            text = path.read_text(
                errors="replace",
            )
        except OSError:
            continue

        for entry in compute_task_list_entries(
            text,
        ):
            entries.append(
                ProjectTaskEntry(
                    path=path,
                    tag=entry.tag,
                    line=entry.line,
                    column=entry.column,
                    text=entry.text,
                )
            )

    return tuple(
        entries,
    )
