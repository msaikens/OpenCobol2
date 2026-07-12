"""Command handlers connecting File/Project menu commands to the shell."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QWidget,
)

from opencobol2.commands import (
    CommandContext,
    CommandHandler,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import (
    Project,
    ProjectStorage,
)


def open_project_from_path(
    project_explorer: ProjectExplorerWidget,
    project_path: Path,
) -> Project:
    """Load a project file from disk and display it in the Project Explorer."""

    project = ProjectStorage(
        project_path,
    ).load()
    project_explorer.set_project(
        project,
    )

    return project


def create_project_open_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that prompts for a project file and opens it."""

    def handle_open_project(
        context: CommandContext,
    ) -> Project | None:
        parent_widget = (
            parent_widget_provider()
        )

        path_str, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Open Project",
            "",
            (
                "OpenCobol2 Project Files (*.json);;"
                "All Files (*)"
            ),
        )

        if not path_str:
            return None

        try:
            return open_project_from_path(
                project_explorer,
                Path(
                    path_str,
                ),
            )
        except (
            OSError,
            ValueError,
        ) as error:
            QMessageBox.critical(
                parent_widget,
                "Open Project Failed",
                str(
                    error,
                ),
            )
            return None

    return handle_open_project


def create_project_close_handler(
    *,
    project_explorer: ProjectExplorerWidget,
) -> CommandHandler:
    """Create a handler that closes the currently open project."""

    def handle_close_project(
        context: CommandContext,
    ) -> None:
        project_explorer.set_project(
            None,
        )

    return handle_close_project
