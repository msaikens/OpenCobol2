"""Bootstraps and launches the OpenCobol2 desktop application shell."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication

from opencobol2.accessibility import AccessibilityProfileRegistry
from opencobol2.commands import CommandContext
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
from opencobol2.documents import DocumentService
from opencobol2.gui.build_commands import (
    create_build_project_handler,
)
from opencobol2.gui.command_palette import (
    create_show_command_palette_handler,
)
from opencobol2.gui.compiler_profiles_dialog import (
    create_show_compiler_profiles_handler,
)
from opencobol2.gui.bookmarks_panel import BookmarksWidget
from opencobol2.gui.editor import EditorTabsWidget
from opencobol2.gui.find_results_panel import FindResultsWidget
from opencobol2.gui.git_changes import GitChangesWidget
from opencobol2.gui.git_repository import GitRepositoryWidget
from opencobol2.gui.main_window import MainWindow
from opencobol2.gui.outline_panel import OutlineWidget
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
from opencobol2.gui.project_properties_dialog import (
    ProjectPropertiesDialog,
)
from opencobol2.gui.search_commands import (
    create_find_in_files_handler,
)
from opencobol2.gui.settings_dialog import (
    create_show_settings_handler,
)
from opencobol2.gui.task_list_commands import scan_project_for_tasks
from opencobol2.gui.task_list_panel import TaskListWidget
from opencobol2.gui.terminal_panel import TerminalWidget
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


def _resolve_git_executable_path(
    settings: ApplicationSettings,
) -> str:
    """Return the configured Git executable, defaulting to `"git"`."""

    configured_path = (
        settings.external_tools.git_executable_path
    )

    return (
        "git"
        if configured_path is None
        else str(configured_path)
    )


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


def _recent_project_paths(
    settings_service: SettingsService,
) -> tuple[Path, ...]:
    """Return persisted recent-project paths that still exist on disk."""

    return tuple(
        path
        for path in (
            settings_service
            .current
            .recent_projects
            .paths
        )
        if path.is_file()
    )


def create_main_window(
    *,
    settings_service: SettingsService | None = None,
    project: Project | None = None,
) -> MainWindow:
    """Wire the built-in OpenCobol2 registries and construct the main window.

    The main window's central widget is a real `EditorTabsWidget` backed by
    a `DocumentService`: double-clicking a physical file in Project Explorer
    opens it in a tab, and File > New/Open/Save/Save As/Save All/Close/Close
    All are all wired to real handlers (dirty tracking, unsaved-changes
    prompts on close, Save As for untitled documents). Open Recent File
    still lists nothing yet — unlike Open Recent Project, there is no
    persisted recent-files list wired up yet. Recent-project menus are real:
    every successful New/Open/Save-As records that project file, and File >
    Open Recent Project lists them (skipping any that no longer exist on
    disk). `project` seeds the Project Explorer panel; File > New/Open/Close
    Project and File > Save Project As are all wired to real handlers that
    create, load, save, or clear a project file and update that panel. The
    status bar shows the open project's name (left) and the active theme
    (right), refreshing automatically whenever the project changes. The Git
    Changes and Git Repository panels both track a Git repository
    discovered at the open project's root — falling back to their empty
    state if there is none, or if `git` itself is unavailable — refreshing
    automatically alongside it. Build > Build Project compiles every
    `.cbl`/`.cob` file found under the open project's root (honoring
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

    # Built before the editor and command registry below (unlike most other
    # services) because nothing about it depends on them, and both the
    # editor's initial colors and the Settings dialog's handler need a live
    # ThemeService to read and switch themes.
    theme_service = ThemeService(
        registry=create_builtin_theme_registry(),
        initial_theme_id=(
            resolved_settings_service
            .current
            .theme
            .active_theme_id
        ),
    )

    project_explorer = ProjectExplorerWidget(
        project,
    )

    document_service = DocumentService()
    editor_tabs_widget = EditorTabsWidget(
        document_service=document_service,
        theme=theme_service.active_theme,
        editor_settings=(
            resolved_settings_service.current.editor
        ),
        guide_settings=(
            resolved_settings_service
            .current
            .cobol
            .guides
        ),
    )
    project_explorer.file_double_clicked.connect(
        editor_tabs_widget.open_path,
    )

    git_service = GitService(
        executable_path=_resolve_git_executable_path(
            resolved_settings_service.current,
        ),
    )
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
    find_results_widget = FindResultsWidget()
    terminal_widget = TerminalWidget(
        working_directory=(
            project.root_path
            if project is not None
            else None
        ),
    )
    outline_widget = OutlineWidget()
    task_list_widget = TaskListWidget()
    bookmarks_widget = BookmarksWidget()

    compiler_provider_registry = (
        create_builtin_compiler_provider_registry()
    )

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
                    compiler_provider_registry
                ),
            ),
            runtime_factory_registry=compiler_runtime_registry,
        )
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

    def _reveal_find_results() -> None:
        """Force the Find Results dock panel visible after a search runs.

        `ToolWindowService.activate()` only updates domain state; nothing
        currently syncs that state back to the real `QDockWidget` (the dock
        manager only listens the other way, dock -> service). Show/raise the
        dock widget directly instead, since a search whose results stay
        hidden would look like it silently did nothing.
        """

        main_window = main_window_holder[0]

        if main_window is None:
            return

        dock_widget = (
            main_window.dock_manager.get_dock_widget(
                BuiltInToolWindowIds.FIND_RESULTS,
            )
        )
        dock_widget.setVisible(
            True,
        )
        dock_widget.raise_()

    def _handle_find_all_references() -> None:
        """Find every reference to whatever the active tab's cursor is on."""

        results = (
            editor_tabs_widget.find_references_for_active_tab()
        )
        find_results_widget.set_results(
            results,
        )
        _reveal_find_results()

    def _handle_file_print() -> None:
        """Print the active tab's document contents, after a Print dialog."""

        printer = QPrinter()
        dialog = QPrintDialog(
            printer,
            main_window_holder[0],
        )

        if (
            dialog.exec()
            == QPrintDialog.DialogCode.Accepted
        ):
            editor_tabs_widget.print_active_tab(
                printer,
            )

    def _handle_show_project_properties() -> None:
        """Open Project Properties for the currently displayed project."""

        current_project = project_explorer.project

        if current_project is None:
            return

        dialog = ProjectPropertiesDialog(
            project=current_project,
            settings_service=resolved_settings_service,
            parent=main_window_holder[0],
        )

        if dialog.exec():
            project_explorer.set_project(
                dialog.updated_project,
            )

    project_explorer.project_properties_requested.connect(
        _handle_show_project_properties,
    )

    def _apply_settings_to_running_window(
        settings: ApplicationSettings,
    ) -> None:
        """Reflect newly-saved settings onto the already-built shell."""

        theme_service.set_active_theme(
            settings.theme.active_theme_id,
        )
        main_window_holder[0].apply_active_theme()
        editor_tabs_widget.apply_theme(
            theme_service.active_theme,
        )
        editor_tabs_widget.apply_editor_settings(
            settings.editor,
        )
        editor_tabs_widget.apply_guide_settings(
            settings.cobol.guides,
        )

        git_service.set_executable_path(
            _resolve_git_executable_path(
                settings,
            ),
        )

    command_service = CommandService(
        registry=create_builtin_command_registry(
            tool_window_service=tool_window_service,
            accessibility_service=accessibility_service,
            handlers=BuiltInCommandHandlers(
                values={
                    BuiltInCommandIds.FILE_NEW: (
                        lambda context: (
                            editor_tabs_widget.new_file()
                        )
                    ),
                    BuiltInCommandIds.FILE_OPEN: (
                        lambda context: (
                            editor_tabs_widget.open_file_dialog()
                        )
                    ),
                    BuiltInCommandIds.FILE_SAVE: (
                        lambda context: (
                            editor_tabs_widget.save_active_document()
                        )
                    ),
                    BuiltInCommandIds.FILE_SAVE_AS: (
                        lambda context: (
                            editor_tabs_widget.save_active_document_as()
                        )
                    ),
                    BuiltInCommandIds.FILE_SAVE_ALL: (
                        lambda context: (
                            editor_tabs_widget.save_all_documents()
                        )
                    ),
                    BuiltInCommandIds.FILE_PRINT: (
                        lambda context: (
                            _handle_file_print()
                        )
                    ),
                    BuiltInCommandIds.FILE_CLOSE: (
                        lambda context: (
                            editor_tabs_widget.close_active_document()
                        )
                    ),
                    BuiltInCommandIds.FILE_CLOSE_ALL: (
                        lambda context: (
                            editor_tabs_widget.close_all_documents()
                        )
                    ),
                    BuiltInCommandIds.EDIT_FIND: (
                        lambda context: (
                            editor_tabs_widget.show_find()
                        )
                    ),
                    BuiltInCommandIds.EDIT_REPLACE: (
                        lambda context: (
                            editor_tabs_widget.show_replace()
                        )
                    ),
                    BuiltInCommandIds.EDIT_FIND_IN_FILES: (
                        create_find_in_files_handler(
                            project_explorer=project_explorer,
                            find_results_widget=(
                                find_results_widget
                            ),
                            reveal_find_results=(
                                _reveal_find_results
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.EDIT_TOGGLE_BOOKMARK: (
                        lambda context: (
                            editor_tabs_widget.toggle_bookmark_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_GO_TO_DEFINITION: (
                        lambda context: (
                            editor_tabs_widget.go_to_definition_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_FIND_ALL_REFERENCES: (
                        lambda context: (
                            _handle_find_all_references()
                        )
                    ),
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
                    BuiltInCommandIds.TOOLS_COMPILER_PROFILES: (
                        create_show_compiler_profiles_handler(
                            settings_service=(
                                resolved_settings_service
                            ),
                            provider_registry=(
                                compiler_provider_registry
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
            BuiltInToolWindowIds.FIND_RESULTS: (
                lambda: find_results_widget
            ),
            BuiltInToolWindowIds.TERMINAL: (
                lambda: terminal_widget
            ),
            BuiltInToolWindowIds.OUTLINE: (
                lambda: outline_widget
            ),
            BuiltInToolWindowIds.TASK_LIST: (
                lambda: task_list_widget
            ),
            BuiltInToolWindowIds.BOOKMARKS: (
                lambda: bookmarks_widget
            ),
        },
        status_bar_service=status_bar_service,
        central_widget=editor_tabs_widget,
    )
    main_window_holder[0] = window

    def _refresh_task_list() -> None:
        current_project = project_explorer.project

        if current_project is None:
            task_list_widget.clear_tasks()
            return

        task_list_widget.set_tasks(
            scan_project_for_tasks(
                current_project,
            )
        )

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
        editor_tabs_widget.welcome_page.set_recent_projects(
            _recent_project_paths(
                resolved_settings_service,
            )
        )
        terminal_widget.set_working_directory(
            changed_project.root_path
            if changed_project is not None
            else None
        )
        _refresh_task_list()

    project_explorer.project_changed.connect(
        _on_project_changed,
    )

    def _handle_welcome_new_project() -> None:
        command_service_holder[0].execute(
            BuiltInCommandIds.PROJECT_NEW,
        )

    def _handle_welcome_open_project() -> None:
        command_service_holder[0].execute(
            BuiltInCommandIds.PROJECT_OPEN,
        )

    def _handle_welcome_open_recent_project(
        project_path: Path,
    ) -> None:
        command_service_holder[0].execute(
            BuiltInCommandIds.PROJECT_OPEN_RECENT,
            CommandContext(
                values={
                    "path": str(
                        project_path,
                    ),
                },
            ),
        )

    welcome_page = editor_tabs_widget.welcome_page
    welcome_page.new_project_requested.connect(
        _handle_welcome_new_project,
    )
    welcome_page.open_project_requested.connect(
        _handle_welcome_open_project,
    )
    welcome_page.open_recent_project_requested.connect(
        _handle_welcome_open_recent_project,
    )
    welcome_page.set_recent_projects(
        _recent_project_paths(
            resolved_settings_service,
        )
    )

    def _handle_find_result_activated(
        path: Path,
        line: int,
        column: int,
    ) -> None:
        editor_tabs_widget.open_path_at_line(
            path,
            line,
            column,
        )

    find_results_widget.result_activated.connect(
        _handle_find_result_activated,
    )

    def _refresh_outline() -> None:
        outline_widget.set_outline(
            editor_tabs_widget.current_outline(),
        )

    def _refresh_live_diagnostics() -> None:
        problems_widget.set_live_diagnostics(
            editor_tabs_widget.current_diagnostics(),
        )

    def _handle_active_document_changed() -> None:
        _refresh_outline()
        _refresh_live_diagnostics()

    editor_tabs_widget.active_document_changed.connect(
        _handle_active_document_changed,
    )
    outline_widget.line_activated.connect(
        editor_tabs_widget.go_to_active_line,
    )

    def _handle_task_entry_activated(
        path: Path,
        line: int,
        column: int,
    ) -> None:
        editor_tabs_widget.open_path_at_line(
            path,
            line,
            column,
        )

    task_list_widget.refresh_requested.connect(
        _refresh_task_list,
    )
    task_list_widget.entry_activated.connect(
        _handle_task_entry_activated,
    )
    _refresh_task_list()

    def _refresh_bookmarks() -> None:
        bookmarks_widget.set_bookmarks(
            editor_tabs_widget.all_bookmarks(),
        )

    editor_tabs_widget.bookmarks_changed.connect(
        _refresh_bookmarks,
    )
    bookmarks_widget.entry_activated.connect(
        editor_tabs_widget.reveal_bookmark,
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
