"""Command handlers connecting File/Project menu commands to the shell."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
)

from opencobol2.commands import (
    CommandContext,
    CommandHandler,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import (
    create_project,
    Project,
    ProjectStorage,
)


_PROJECT_FILE_FILTER = (
    "OpenCobol2 Project Files (*.json);;"
    "All Files (*)"
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
            _PROJECT_FILE_FILTER,
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


def create_project_from_details(
    name: str,
    root_path: Path,
    project_file: Path,
) -> Project:
    """Create a new project and persist it to a project file."""

    project = create_project(
        name=name,
        root_path=root_path,
    )
    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    return project


def save_project_as(
    project: Project,
    project_file: Path,
) -> Project:
    """Persist an existing project to a new project file location."""

    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    return project


def create_project_new_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that prompts for new-project details and creates it."""

    def handle_new_project(
        context: CommandContext,
    ) -> Project | None:
        parent_widget = (
            parent_widget_provider()
        )

        name, ok = QInputDialog.getText(
            parent_widget,
            "New Project",
            "Project name:",
        )

        if not ok or not name.strip():
            return None

        root_path_str = QFileDialog.getExistingDirectory(
            parent_widget,
            "Select Project Root Directory",
        )

        if not root_path_str:
            return None

        project_file_str, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Save Project As",
            "",
            _PROJECT_FILE_FILTER,
        )

        if not project_file_str:
            return None

        try:
            project = create_project_from_details(
                name,
                Path(
                    root_path_str,
                ),
                Path(
                    project_file_str,
                ),
            )
            project_explorer.set_project(
                project,
            )

            return project
        except (
            OSError,
            ValueError,
        ) as error:
            QMessageBox.critical(
                parent_widget,
                "New Project Failed",
                str(
                    error,
                ),
            )
            return None

    return handle_new_project


def create_project_save_as_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that saves the open project to a new location."""

    def handle_save_project_as(
        context: CommandContext,
    ) -> Project | None:
        parent_widget = (
            parent_widget_provider()
        )
        current_project = (
            project_explorer.project
        )

        if current_project is None:
            QMessageBox.information(
                parent_widget,
                "Save Project As",
                "No project is open to save.",
            )
            return None

        project_file_str, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Save Project As",
            "",
            _PROJECT_FILE_FILTER,
        )

        if not project_file_str:
            return None

        try:
            return save_project_as(
                current_project,
                Path(
                    project_file_str,
                ),
            )
        except OSError as error:
            QMessageBox.critical(
                parent_widget,
                "Save Project Failed",
                str(
                    error,
                ),
            )
            return None

    return handle_save_project_as
