"""Bootstraps and launches the OpenCobol2 desktop application shell."""

from __future__ import annotations

from pathlib import Path
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
from opencobol2.compiler.providers import (
    create_builtin_compiler_provider_registry,
)
from opencobol2.compiler.runtimes import (
    CompilerRuntimeFactoryRegistry,
    CustomLocalCompilerRuntimeFactory,
    GnuCobolRuntimeFactory,
)
from opencobol2.gui.build_commands import (
    create_build_project_handler,
)
from opencobol2.gui.command_palette import (
    create_show_command_palette_handler,
)
from opencobol2.gui.git_changes import GitChangesWidget
from opencobol2.gui.git_repository import GitRepositoryWidget
from opencobol2.gui.main_window import MainWindow
from opencobol2.gui.output_panel import OutputWidget
from opencobol2.gui.problems_panel import ProblemsWidget
from opencobol2.gui.project_commands import (
    create_project_close_handler,
    create_project_new_handler,
    create_project_open_handler,
    create_project_open_recent_handler,
    create_project_save_as_handler,
    create_recent_project_provider,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.gui.settings_dialog import (
    create_show_settings_handler,
)
from opencobol2.project import Project
from opencobol2.services.accessibility import AccessibilityService
from opencobol2.services.command_contributions import (
    CommandContributionService,
)
from opencobol2.services.commands import CommandService
from opencobol2.services.compiler_runtimes import (
    CompilerRuntimeActivationService,
)
from opencobol2.services.compilers import CompilerProfileService
from opencobol2.services.git import (
    GitCommandFailedError,
    GitCommandTimedOutError,
    GitExecutableUnavailableError,
    GitRepositoryNotFoundError,
    GitService,
)
from opencobol2.services.status_bar import StatusBarService
from opencobol2.services.theming import ThemeService
from opencobol2.services.tool_windows import ToolWindowService
from opencobol2.services.toolchains import GnuCobolToolchainService
from opencobol2.settings import (
    ApplicationSettings,
    SettingsService,
)
from opencobol2.status_bar import (
    StatusBarItemAlignment,
    StatusBarItemContent,
    StatusBarItemDefinition,
    StatusBarItemRegistry,
)
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


def _create_status_bar_registry(
    *,
    project_explorer: ProjectExplorerWidget,
    theme_service: ThemeService,
) -> StatusBarItemRegistry:
    """Create the built-in status bar items: current project and theme."""

    registry = StatusBarItemRegistry()

    def _project_content() -> StatusBarItemContent:
        project = project_explorer.project

        return StatusBarItemContent(
            text=(
                f"Project: {project.name}"
                if project is not None
                else "No Project Open"
            ),
        )

    def _theme_content() -> StatusBarItemContent:
        return StatusBarItemContent(
            text=(
                "Theme: "
                f"{theme_service.active_theme.display_name}"
            ),
        )

    registry.register(
        StatusBarItemDefinition(
            item_id="project",
            alignment=StatusBarItemAlignment.LEFT,
            provider=_project_content,
            order=10,
        )
    )
    registry.register(
        StatusBarItemDefinition(
            item_id="theme",
            alignment=StatusBarItemAlignment.RIGHT,
            provider=_theme_content,
            order=10,
        )
    )

    return registry


def _discover_repository_path(
    git_service: GitService,
    project: Project | None,
) -> Path | None:
    """Best-effort discovery of a Git repository at a project's root.

    Returns `None` for no project, a non-repository root, a missing `git`
    executable, or any other Git command failure — the Git Changes panel
    degrades to its empty state rather than the bootstrap crashing outright.
    """

    if project is None:
        return None

    try:
        return git_service.discover_repository(
            project.root_path,
        )
    except (
        GitRepositoryNotFoundError,
        GitExecutableUnavailableError,
        GitCommandFailedError,
        GitCommandTimedOutError,
    ):
        return None


def create_main_window(
    *,
    settings_service: SettingsService | None = None,
    project: Project | None = None,
) -> MainWindow:
    """Wire the built-in OpenCobol2 registries and construct the main window.

    Recent-file menus start empty: OpenCobol2 has no document/file model
    yet, so there's nothing to make that one real. Recent-project menus are
    real: every successful New/Open/Save-As records that project file, and
    File > Open Recent Project lists them (skipping any that no longer
    exist on disk). `project` seeds the Project Explorer panel; File >
    New/Open/Close Project and File > Save Project As are all wired to real
    handlers that create, load, save, or clear a project file and update
    that panel. The status bar shows the open project's name (left) and the
    active theme (right), refreshing automatically whenever the project
    changes. The Git Changes and Git Repository panels both track a Git
    repository discovered at the open project's root — falling back to
    their empty state if there is none, or if `git` itself is unavailable —
    refreshing automatically alongside it. Build > Build Project compiles
    every `.cbl`/`.cob` file found under the open project's root (honoring
    `excluded_patterns`) using the default configured compiler profile
    (GnuCOBOL auto-discovery or a custom local compiler), logging process
    output to the Output panel and parsed diagnostics to the Problems panel.
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

    git_service = GitService()
    initial_repository_path = _discover_repository_path(
        git_service,
        project,
    )
    git_changes_widget = GitChangesWidget(
        git_service=git_service,
        repository_path=initial_repository_path,
    )
    git_repository_widget = GitRepositoryWidget(
        git_service=git_service,
        repository_path=initial_repository_path,
    )

    output_widget = OutputWidget()
    problems_widget = ProblemsWidget()

    compiler_runtime_registry = CompilerRuntimeFactoryRegistry()
    compiler_runtime_registry.register(
        GnuCobolRuntimeFactory(
            toolchain_service=GnuCobolToolchainService(
                settings_service=resolved_settings_service,
            ),
        ),
    )
    compiler_runtime_registry.register(
        CustomLocalCompilerRuntimeFactory(),
    )
    compiler_runtime_activation_service = (
        CompilerRuntimeActivationService(
            profile_service=CompilerProfileService(
                settings_service=resolved_settings_service,
                provider_registry=(
                    create_builtin_compiler_provider_registry()
                ),
            ),
            runtime_factory_registry=compiler_runtime_registry,
        )
    )

    # Built before the command registry (unlike CommandService/MainWindow
    # below) because nothing about it depends on that registry, and the
    # Settings dialog's handler needs a live ThemeService to switch themes.
    theme_service = ThemeService(
        registry=create_builtin_theme_registry(),
        initial_theme_id=(
            resolved_settings_service
            .current
            .theme
            .active_theme_id
        ),
    )

    # MainWindow doesn't exist until after the command registry below, but
    # the Open Project dialog needs it as a parent; this cell is filled in
    # once construction finishes and only read later, when a user actually
    # triggers the command.
    main_window_holder: list[
        MainWindow | None
    ] = [None]
    # Same problem in reverse: the command palette needs the CommandService
    # that wraps THIS registry, which doesn't exist until after the registry
    # it's being registered into is fully built.
    command_service_holder: list[
        CommandService | None
    ] = [None]

    def _apply_settings_to_running_window(
        settings: ApplicationSettings,
    ) -> None:
        """Reflect newly-saved settings onto the already-built shell."""

        theme_service.set_active_theme(
            settings.theme.active_theme_id,
        )
        main_window_holder[0].apply_active_theme()

    command_service = CommandService(
        registry=create_builtin_command_registry(
            tool_window_service=tool_window_service,
            accessibility_service=accessibility_service,
            handlers=BuiltInCommandHandlers(
                values={
                    BuiltInCommandIds.PROJECT_OPEN: (
                        create_project_open_handler(
                            project_explorer=project_explorer,
                            settings_service=(
                                resolved_settings_service
                            ),
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
                            settings_service=(
                                resolved_settings_service
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.PROJECT_SAVE_AS: (
                        create_project_save_as_handler(
                            project_explorer=project_explorer,
                            settings_service=(
                                resolved_settings_service
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.PROJECT_OPEN_RECENT: (
                        create_project_open_recent_handler(
                            project_explorer=project_explorer,
                            settings_service=(
                                resolved_settings_service
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.VIEW_COMMAND_PALETTE: (
                        create_show_command_palette_handler(
                            command_service_provider=(
                                lambda: command_service_holder[0]
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.TOOLS_SETTINGS: (
                        create_show_settings_handler(
                            settings_service=(
                                resolved_settings_service
                            ),
                            theme_registry=(
                                theme_service.registry
                            ),
                            on_applied=(
                                _apply_settings_to_running_window
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.BUILD_PROJECT: (
                        create_build_project_handler(
                            project_explorer=project_explorer,
                            output_widget=output_widget,
                            problems_widget=problems_widget,
                            runtime_activation_service=(
                                compiler_runtime_activation_service
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                },
            ),
        ),
    )
    command_service_holder[0] = command_service

    contribution_service = CommandContributionService(
        command_service=command_service,
        contribution_registry=(
            create_builtin_command_contribution_registry(
                recent_file_provider=lambda context: (),
                recent_project_provider=(
                    create_recent_project_provider(
                        resolved_settings_service,
                    )
                ),
                accessibility_service=accessibility_service,
            )
        ),
    )

    status_bar_service = StatusBarService(
        registry=_create_status_bar_registry(
            project_explorer=project_explorer,
            theme_service=theme_service,
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
            BuiltInToolWindowIds.GIT_CHANGES: (
                lambda: git_changes_widget
            ),
            BuiltInToolWindowIds.GIT_REPOSITORY: (
                lambda: git_repository_widget
            ),
            BuiltInToolWindowIds.OUTPUT: (
                lambda: output_widget
            ),
            BuiltInToolWindowIds.PROBLEMS: (
                lambda: problems_widget
            ),
        },
        status_bar_service=status_bar_service,
    )
    main_window_holder[0] = window

    def _on_project_changed(
        changed_project: Project | None,
    ) -> None:
        """Refresh everything derived from the project when it changes."""

        window.refresh_status_bar()

        repository_path = _discover_repository_path(
            git_service,
            changed_project,
        )
        git_changes_widget.set_repository_path(
            repository_path,
        )
        git_repository_widget.set_repository_path(
            repository_path,
        )

    project_explorer.project_changed.connect(
        _on_project_changed,
    )

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
