"""Command handlers connecting File/Project menu commands to the shell."""

from __future__ import annotations

from collections.abc import Callable, Iterable
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
    DynamicMenuItem,
)
from opencobol2.commands.builtins import BuiltInCommandIds
from opencobol2.gui.editor import EditorTabsWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import (
    create_project,
    Project,
    ProjectStorage,
)
from opencobol2.settings import SettingsService


_PROJECT_FILE_FILTER = (
    "OpenCobol2 Project Files (*.json);;"
    "All Files (*)"
)


def record_recent_project(
    settings_service: SettingsService,
    project_path: Path,
) -> None:
    """Move a project file to the front of the persisted recent-projects list."""

    updated_recent_projects = (
        settings_service
        .current
        .recent_projects
        .with_recorded_path(
            project_path,
        )
    )
    settings_service.update_recent_projects(
        updated_recent_projects,
    )


def open_project_from_path(
    project_explorer: ProjectExplorerWidget,
    project_path: Path,
    *,
    settings_service: SettingsService | None = None,
) -> Project:
    """Load a project file from disk and display it in the Project Explorer.

    Recent-project state is recorded *before* the project is handed to the
    explorer: `set_project` synchronously emits `project_changed`, and any
    listener refreshing itself from `settings_service.current.recent_projects`
    (e.g. the Welcome page) must see the just-opened path already recorded.
    """

    project = ProjectStorage(
        project_path,
    ).load()

    if settings_service is not None:
        record_recent_project(
            settings_service,
            project_path,
        )

    project_explorer.set_project(
        project,
    )

    return project


def create_project_open_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    settings_service: SettingsService | None = None,
    project_file_path_holder: list[Path | None] | None = None,
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

        project_path = Path(
            path_str,
        )

        try:
            project = open_project_from_path(
                project_explorer,
                project_path,
                settings_service=settings_service,
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

        if project_file_path_holder is not None:
            project_file_path_holder[0] = project_path

        return project

    return handle_open_project


def create_project_close_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    editor_tabs_widget: EditorTabsWidget | None = None,
    project_file_path_holder: list[Path | None] | None = None,
) -> CommandHandler:
    """Create a handler that closes the currently open project.

    Editor §UIBootstrap-3: closing a project used to leave that
    project's open editor tabs (and everything derived from them --
    bookmarks, breakpoints, outline, debug state) completely
    untouched, with no indication their owning project was gone.
    `editor_tabs_widget`, when given, closes every open tab first
    (reusing `close_all_documents()`'s existing unsaved-changes
    Save/Discard/Cancel prompting) before the project itself closes --
    optional only so existing callers that construct this handler
    without an editor (if any) keep working unchanged.
    """

    def handle_close_project(
        context: CommandContext,
    ) -> None:
        if editor_tabs_widget is not None:
            editor_tabs_widget.close_all_documents()

        project_explorer.set_project(
            None,
        )

        if project_file_path_holder is not None:
            project_file_path_holder[0] = None

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
    settings_service: SettingsService | None = None,
    project_file_path_holder: list[Path | None] | None = None,
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

        project_file = Path(
            project_file_str,
        )

        try:
            project = create_project_from_details(
                name,
                Path(
                    root_path_str,
                ),
                project_file,
            )
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

        if settings_service is not None:
            record_recent_project(
                settings_service,
                project_file,
            )

        project_explorer.set_project(
            project,
        )

        if project_file_path_holder is not None:
            project_file_path_holder[0] = project_file

        return project

    return handle_new_project


def create_project_save_as_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    settings_service: SettingsService | None = None,
    project_file_path_holder: list[Path | None] | None = None,
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

        project_file = Path(
            project_file_str,
        )

        try:
            saved_project = save_project_as(
                current_project,
                project_file,
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

        if settings_service is not None:
            record_recent_project(
                settings_service,
                project_file,
            )

        if project_file_path_holder is not None:
            project_file_path_holder[0] = project_file

        return saved_project

    return handle_save_project_as


def create_recent_project_provider(
    settings_service: SettingsService,
) -> Callable[
    [CommandContext],
    Iterable[DynamicMenuItem],
]:
    """Create a dynamic menu provider listing recent, still-existing project files."""

    def provide_recent_projects(
        context: CommandContext,
    ) -> Iterable[DynamicMenuItem]:
        return tuple(
            DynamicMenuItem(
                title=str(
                    path,
                ),
                command_id=(
                    BuiltInCommandIds.PROJECT_OPEN_RECENT
                ),
                context=CommandContext(
                    values={
                        "path": str(
                            path,
                        ),
                    },
                ),
            )
            for path in (
                settings_service
                .current
                .recent_projects
                .paths
            )
            if path.is_file()
        )

    return provide_recent_projects


def create_project_open_recent_handler(
    *,
    project_explorer: ProjectExplorerWidget,
    settings_service: SettingsService,
    project_file_path_holder: list[Path | None] | None = None,
    parent_widget_provider: Callable[
        [],
        QWidget | None,
    ] = lambda: None,
) -> CommandHandler:
    """Create a handler that opens a project referenced by a recent-item click."""

    def handle_open_recent_project(
        context: CommandContext,
    ) -> Project | None:
        parent_widget = (
            parent_widget_provider()
        )
        project_path = Path(
            context.require(
                "path",
            ),
        )

        try:
            project = open_project_from_path(
                project_explorer,
                project_path,
                settings_service=settings_service,
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

        if project_file_path_holder is not None:
            project_file_path_holder[0] = project_path

        return project

    return handle_open_recent_project
