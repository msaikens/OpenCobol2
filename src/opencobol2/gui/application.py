"""Bootstraps and launches the OpenCobol2 desktop application shell."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from opencobol2.accessibility import AccessibilityProfileRegistry
from opencobol2.commands.builtins import (
    BuiltInCommandSurfaceIds,
    create_builtin_command_contribution_registry,
    create_builtin_command_registry,
)
from opencobol2.gui.main_window import MainWindow
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
    `project` seeds the Project Explorer panel; there is no "Open Project"
    command wired up yet to load one interactively.
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

    command_service = CommandService(
        registry=create_builtin_command_registry(
            tool_window_service=tool_window_service,
            accessibility_service=accessibility_service,
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

    return MainWindow(
        contribution_service=contribution_service,
        tool_window_service=tool_window_service,
        theme_service=theme_service,
        top_level_menus=TOP_LEVEL_MENUS,
        tool_window_content_factories={
            BuiltInToolWindowIds.PROJECT_EXPLORER: (
                lambda: ProjectExplorerWidget(
                    project,
                )
            ),
        },
    )


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
