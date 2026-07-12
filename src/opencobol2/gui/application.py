"""Bootstraps and launches the OpenCobol2 desktop application shell."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from opencobol2.accessibility import AccessibilityProfileRegistry
from opencobol2.commands.builtins import (
    BuiltInCommandHandlers,
    BuiltInCommandIds,
    BuiltInCommandSurfaceIds,
    create_builtin_command_contribution_registry,
    create_builtin_command_registry,
)
from opencobol2.gui.main_window import MainWindow
from opencobol2.gui.project_commands import (
    create_project_close_handler,
    create_project_new_handler,
    create_project_open_handler,
    create_project_save_as_handler,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import Project
from opencobol2.services.accessibility import AccessibilityService
from opencobol2.services.command_contributions import (
    CommandContributionService,
)
from opencobol2.services.commands import CommandService
from opencobol2.services.theming import ThemeService
from opencobol2.services.tool_windows import ToolWindowService
from opencobol2.settings import SettingsService
from opencobol2.theming import create_builtin_theme_registry
from opencobol2.tool_windows.builtins import (
    BuiltInToolWindowIds,
    create_builtin_tool_window_registry,
)


TOP_LEVEL_MENUS = (
    (
        BuiltInCommandSurfaceIds.FILE,
        "&File",
    ),
    (
        BuiltInCommandSurfaceIds.EDIT,
        "&Edit",
    ),
    (
        BuiltInCommandSurfaceIds.VIEW,
        "&View",
    ),
    (
        BuiltInCommandSurfaceIds.BUILD,
        "&Build",
    ),
    (
        BuiltInCommandSurfaceIds.GIT,
        "&Git",
    ),
    (
        BuiltInCommandSurfaceIds.TOOLS,
        "&Tools",
    ),
    (
        BuiltInCommandSurfaceIds.ACCESSIBILITY,
        "&Accessibility",
    ),
    (
        BuiltInCommandSurfaceIds.HELP,
        "&Help",
    ),
)


def create_main_window(
    *,
    settings_service: SettingsService | None = None,
    project: Project | None = None,
) -> MainWindow:
    """Wire the built-in OpenCobol2 registries and construct the main window.

    Recent-file and recent-project menus start empty: neither is persisted
    yet, so wiring real providers is future work, not this bootstrap's job.
    `project` seeds the Project Explorer panel; File > New/Open/Close
    Project and File > Save Project As are all wired to real handlers that
    create, load, save, or clear a project file and update that panel.
    """

    resolved_settings_service = (
        SettingsService()
        if settings_service is None
        else settings_service
    )

    tool_window_service = ToolWindowService(
        registry=create_builtin_tool_window_registry(),
    )

    accessibility_service = AccessibilityService(
        profile_registry=AccessibilityProfileRegistry(),
        tool_window_service=tool_window_service,
    )

    project_explorer = ProjectExplorerWidget(
        project,
    )
    # MainWindow doesn't exist until after the command registry below, but
    # the Open Project dialog needs it as a parent; this cell is filled in
    # once construction finishes and only read later, when a user actually
    # triggers the command.
    main_window_holder: list[
        MainWindow | None
    ] = [None]

    command_service = CommandService(
        registry=create_builtin_command_registry(
            tool_window_service=tool_window_service,
            accessibility_service=accessibility_service,
            handlers=BuiltInCommandHandlers(
                values={
                    BuiltInCommandIds.PROJECT_OPEN: (
                        create_project_open_handler(
                            project_explorer=project_explorer,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.PROJECT_CLOSE: (
                        create_project_close_handler(
                            project_explorer=project_explorer,
                        )
                    ),
                    BuiltInCommandIds.PROJECT_NEW: (
                        create_project_new_handler(
                            project_explorer=project_explorer,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.PROJECT_SAVE_AS: (
                        create_project_save_as_handler(
                            project_explorer=project_explorer,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                },
            ),
        ),
    )

    contribution_service = CommandContributionService(
        command_service=command_service,
        contribution_registry=(
            create_builtin_command_contribution_registry(
                recent_file_provider=lambda context: (),
                recent_project_provider=lambda context: (),
                accessibility_service=accessibility_service,
            )
        ),
    )

    theme_service = ThemeService(
        registry=create_builtin_theme_registry(),
        initial_theme_id=(
            resolved_settings_service
            .current
            .theme
            .active_theme_id
        ),
    )

    window = MainWindow(
        contribution_service=contribution_service,
        tool_window_service=tool_window_service,
        theme_service=theme_service,
        top_level_menus=TOP_LEVEL_MENUS,
        tool_window_content_factories={
            BuiltInToolWindowIds.PROJECT_EXPLORER: (
                lambda: project_explorer
            ),
        },
    )
    main_window_holder[0] = window

    return window


def main() -> int:
    """Launch the OpenCobol2 desktop application."""

    application = (
        QApplication.instance()
        or QApplication(
            sys.argv,
        )
    )

    window = create_main_window()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(
        main(),
    )
