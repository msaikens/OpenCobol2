"""Bootstraps and launches the OpenCobol2 desktop application shell.

Wires the built-in services, panels, dock widgets, and command handlers
together into a single :class:`~opencobol2.gui.main_window.MainWindow`
instance (see :func:`create_main_window`) and exposes the process entry
point (:func:`main`) that the application is launched from.
"""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

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
from opencobol2.debugger.models import StopReason, StoppedEvent
from opencobol2.documents import DocumentService
from opencobol2.gui.build_commands import (
    create_build_project_handler,
    create_clean_project_handler,
    create_rebuild_project_handler,
    create_view_listing_handler,
)
from opencobol2.gui.call_stack_panel import CallStackWidget
from opencobol2.gui.command_palette import (
    create_show_command_palette_handler,
)
from opencobol2.gui.compiler_profiles_dialog import (
    create_show_compiler_profiles_handler,
)
from opencobol2.gui.bookmarks_panel import BookmarksWidget
from opencobol2.gui.breakpoints_panel import BreakpointsWidget
from opencobol2.gui.debug_commands import (
    DEBUG_SESSION_ERRORS,
    collect_local_variables,
    create_debug_continue_handler,
    create_debug_start_handler,
    create_debug_step_into_handler,
    create_debug_step_out_handler,
    create_debug_step_over_handler,
    create_debug_stop_handler,
    evaluate_watch_expressions,
)
from opencobol2.gui.debug_session import DebugSessionController
from opencobol2.gui.editor import (
    EditorTabsWidget,
    SourceEditorWidget,
)
from opencobol2.gui.find_results_panel import FindResultsWidget
from opencobol2.gui.git_changes import GitChangesWidget
from opencobol2.gui.git_commands import (
    create_clone_repository_handler,
    create_create_repository_handler,
    create_fetch_handler,
    create_manage_branches_handler,
    create_pull_handler,
    create_push_handler,
    create_sync_handler,
)
from opencobol2.gui.git_repository import GitRepositoryWidget
from opencobol2.gui.help_commands import (
    create_not_yet_available_handler,
    create_show_about_handler,
    create_show_keyboard_shortcuts_handler,
)
from opencobol2.gui.locals_panel import LocalsWidget
from opencobol2.gui.main_window import MainWindow
from opencobol2.gui.memory_panel import MemoryWidget
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
from opencobol2.gui.registers_panel import RegistersWidget
from opencobol2.gui.task_list_commands import scan_project_for_tasks
from opencobol2.gui.task_list_panel import TaskListWidget
from opencobol2.gui.terminal_panel import TerminalWidget
from opencobol2.gui.threads_panel import ThreadsWidget
from opencobol2.gui.watch_panel import WatchWidget
from opencobol2.project import Project, ProjectStorage
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
from opencobol2.theming import (
    DEFAULT_THEME_ID,
    ThemeNotFoundError,
    create_builtin_theme_registry,
)
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
        BuiltInCommandSurfaceIds.DEBUG,
        "&Debug",
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
    """Create the built-in status bar items: current project and theme.

    :param project_explorer: The panel whose current project backs the
        left-aligned "Project" status bar item.
    :param theme_service: The service whose active theme backs the
        right-aligned "Theme" status bar item.
    :returns: A registry containing the two built-in status bar item
        definitions, ready to pass to :class:`StatusBarService`.
    """

    registry = StatusBarItemRegistry()

    def _project_content() -> StatusBarItemContent:
        """Render the left-aligned "Project" status bar item.

        :returns: Content showing the open project's name, or a
            placeholder if no project is open.
        """

        project = project_explorer.project

        return StatusBarItemContent(
            text=(
                f"Project: {project.name}"
                if project is not None
                else "No Project Open"
            ),
        )

    def _theme_content() -> StatusBarItemContent:
        """Render the right-aligned "Theme" status bar item.

        :returns: Content showing the currently active theme's display
            name.
        """

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
    """Return the configured Git executable, defaulting to `"git"`.

    :param settings: The application settings snapshot to read the
        external-tools configuration from.
    :returns: The user-configured Git executable path, or the literal
        string `"git"` if none is configured (relying on `PATH`
        resolution).
    """

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

    :param git_service: The service used to perform the repository
        discovery.
    :param project: The currently open project, or `None` if no project
        is open.
    :returns: The discovered repository's root path, or `None` if there
        is no open project, the project root is not a Git repository,
        the `git` executable is unavailable, or the discovery command
        otherwise failed.
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
    """Return persisted recent-project paths that still exist on disk.

    :param settings_service: The service whose current settings hold
        the persisted list of recent-project paths.
    :returns: Every persisted recent-project path that still points at
        an existing file, in their persisted order.
    """

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
    Every Debug and most Build/Git/Tools/Help commands are wired to real
    handlers too; before this, everything past Debug Step Out in the
    built-in command handler map simply had no handler configured at all,
    so triggering one raised `BuiltInCommandHandlerNotConfiguredError`
    that PySide6's own slot-exception reporter silently swallowed.

    `ThemeService` is constructed before the editor and the command
    registry (unlike most other services here) because nothing about it
    depends on them, while both the editor's initial colors and the
    Settings dialog's handler need a live `ThemeService` to read and
    switch themes. Its persisted `active_theme_id` is validated against
    the theme registry before use, falling back to `DEFAULT_THEME_ID` on
    a lookup failure: `ThemeService.__init__` resolves that ID eagerly
    and unguarded, so a `settings.json` referencing a since-removed or
    otherwise unregistered theme ID used to crash the entire application
    launch with an uncaught `ThemeNotFoundError`. Every comparable
    resolution elsewhere in this function (compiler profiles, Git
    repository discovery) was already validated with a fallback before
    use; this one wasn't.

    Several single-element mutable list "cells" are threaded through the
    closures built here, standing in for values that do not exist yet at
    the point they must be captured: `main_window_holder` is filled in
    once the `MainWindow` itself is constructed (dialogs such as Open
    Project need it as a parent, but it is only read later, when a user
    actually triggers the command); `command_service_holder` holds the
    `CommandService` that wraps the very registry it is being registered
    into, for the same reason (the command palette needs it, but it
    cannot exist until after that registry is built); and
    `debug_symbol_table_holder` holds the symbol table a debug session's
    Locals panel needs, which is not known until Start Debugging actually
    compiles something, even though the stopped-signal handler that reads
    it is wired up well before that happens. `project_file_path_holder`
    tracks which file the open project was loaded from — nothing tracked
    this at all before, so even a well-intentioned Project Properties
    persistence fix had no path to save back to without it; every real
    Open/New/Save-As/Open-Recent Project handler updates it, and Close
    Project clears it.

    Clearing the debug side panels (Call Stack, Locals, Threads,
    Registers, Watch, Memory) is connected to `DebugSessionController`'s
    `session_ended` signal rather than duplicated at each call site,
    because `stop()` is the one place every session-ending path — a
    natural program exit as well as the manual Stop Debugging command in
    `debug_commands.py` — already funnels through.

    :param settings_service: The settings service to use, or `None` to
        construct a fresh default one.
    :param project: The project to seed the Project Explorer panel with,
        or `None` to start with no project open.
    :returns: The fully wired :class:`MainWindow`, ready to `show()`.
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

    _builtin_theme_registry = create_builtin_theme_registry()
    _persisted_theme_id = (
        resolved_settings_service
        .current
        .theme
        .active_theme_id
    )

    try:
        _builtin_theme_registry.get(
            _persisted_theme_id,
        )
        _initial_theme_id = _persisted_theme_id
    except ThemeNotFoundError:
        _initial_theme_id = DEFAULT_THEME_ID

    theme_service = ThemeService(
        registry=_builtin_theme_registry,
        initial_theme_id=_initial_theme_id,
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
        source_format=(
            resolved_settings_service
            .current
            .cobol
            .default_source_format
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
    breakpoints_widget = BreakpointsWidget()
    call_stack_widget = CallStackWidget()
    locals_widget = LocalsWidget()
    watch_widget = WatchWidget()
    threads_widget = ThreadsWidget()
    registers_widget = RegistersWidget()
    memory_widget = MemoryWidget()
    debug_controller = DebugSessionController()
    debug_symbol_table_holder: list = [None]

    compiler_provider_registry = (
        create_builtin_compiler_provider_registry()
    )

    gnucobol_toolchain_service = GnuCobolToolchainService(
        settings_service=resolved_settings_service,
    )
    compiler_profile_service = CompilerProfileService(
        settings_service=resolved_settings_service,
        provider_registry=compiler_provider_registry,
    )

    compiler_runtime_registry = CompilerRuntimeFactoryRegistry()
    compiler_runtime_registry.register(
        GnuCobolRuntimeFactory(
            toolchain_service=gnucobol_toolchain_service,
        ),
    )
    compiler_runtime_registry.register(
        CustomLocalCompilerRuntimeFactory(),
    )
    compiler_runtime_activation_service = (
        CompilerRuntimeActivationService(
            profile_service=compiler_profile_service,
            runtime_factory_registry=compiler_runtime_registry,
        )
    )

    main_window_holder: list[
        MainWindow | None
    ] = [None]
    command_service_holder: list[
        CommandService | None
    ] = [None]
    project_file_path_holder: list[
        Path | None
    ] = [None]

    def _reveal_find_results() -> None:
        """Force the Find Results dock panel visible after a search runs.

        `ToolWindowService.activate()` only updates domain state; nothing
        currently syncs that state back to the real `QDockWidget` (the dock
        manager only listens the other way, dock -> service). Show/raise the
        dock widget directly instead, since a search whose results stay
        hidden would look like it silently did nothing.

        :returns: None. Shows and raises the Find Results dock widget, or
            does nothing if `main_window_holder` is not yet populated.
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

    def _reveal_git_repository_panel() -> None:
        """Force the Git Repository dock panel visible, mirroring `_reveal_find_results`.

        :returns: None. Shows and raises the Git Repository dock widget,
            or does nothing if `main_window_holder` is not yet populated.
        """

        main_window = main_window_holder[0]

        if main_window is None:
            return

        dock_widget = (
            main_window.dock_manager.get_dock_widget(
                BuiltInToolWindowIds.GIT_REPOSITORY,
            )
        )
        dock_widget.setVisible(
            True,
        )
        dock_widget.raise_()

    def _handle_find_all_references() -> None:
        """Find every reference to whatever the active tab's cursor is on.

        :returns: None. Populates the Find Results panel with the
            references found and reveals it.
        """

        results = (
            editor_tabs_widget.find_references_for_active_tab()
        )
        find_results_widget.set_results(
            results,
        )
        _reveal_find_results()

    def _handle_rename_symbol() -> None:
        """Prompt for a new name and rename every reference under the cursor.

        :returns: None. Does nothing if the active tab is not a source
            editor, if the cursor is not on a renameable symbol, or if
            the rename dialog is cancelled or given an empty name;
            otherwise renames every reference on the active tab.
        """

        editor = editor_tabs_widget.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return

        locations = editor.references_at_cursor()

        if not locations:
            return

        new_name, accepted = QInputDialog.getText(
            main_window_holder[0],
            "Rename Symbol",
            "New name:",
            text=locations[0].name,
        )
        stripped_new_name = new_name.strip()

        if not accepted or not stripped_new_name:
            return

        editor_tabs_widget.rename_symbol_on_active_tab(
            stripped_new_name,
        )

    def _handle_go_to_line() -> None:
        """Prompt for a line number and move the active tab's cursor there.

        :returns: None. Does nothing if the active tab is not a source
            editor or the dialog is cancelled; otherwise moves the
            active tab's cursor to the chosen line.
        """

        editor = editor_tabs_widget.currentWidget()

        if not isinstance(
            editor,
            SourceEditorWidget,
        ):
            return

        line_count = editor.document().blockCount()
        line_number, accepted = QInputDialog.getInt(
            main_window_holder[0],
            "Go to Line",
            f"Line number (1-{line_count}):",
            1,
            1,
            line_count,
        )

        if not accepted:
            return

        editor_tabs_widget.go_to_line_on_active_tab(
            line_number,
        )

    def _handle_file_print() -> None:
        """Print the active tab's document contents, after a Print dialog.

        :returns: None. Prints the active tab's document if the Print
            dialog is accepted; does nothing if it is cancelled.
        """

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
        """Open Project Properties for the currently displayed project.

        Saves the updated project back to its backing file when the
        dialog is accepted and a backing file is known. This used to
        only update in-memory state — reloading the same project file
        afterward showed the change was completely discarded, with no
        separate "Save Project" command anywhere to perform one instead.
        `project_file_path_holder` is unset only for a project seeded
        directly into :func:`create_main_window` with no known backing
        file (mainly a test/embedding scenario); there is genuinely
        nowhere to save back to in that case, so the save is skipped.

        :returns: None. Updates the Project Explorer panel with the
            edited project, and persists it to disk when a backing file
            path is known.
        """

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

            project_file_path = (
                project_file_path_holder[0]
            )

            if project_file_path is not None:
                ProjectStorage(
                    project_file_path,
                ).save(
                    dialog.updated_project,
                )

    project_explorer.project_properties_requested.connect(
        _handle_show_project_properties,
    )

    def _apply_settings_to_running_window(
        settings: ApplicationSettings,
    ) -> None:
        """Reflect newly-saved settings onto the already-built shell.

        :param settings: The newly-saved application settings to apply.
        :returns: None. Updates the active theme, the editor's theme,
            editor/guide/source-format settings, and the configured Git
            executable path on the already-constructed widgets and
            services.
        """

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
        editor_tabs_widget.apply_source_format(
            settings.cobol.default_source_format,
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
                    BuiltInCommandIds.EDIT_TOGGLE_BREAKPOINT: (
                        lambda context: (
                            editor_tabs_widget.toggle_breakpoint_on_active_tab()
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
                    BuiltInCommandIds.EDIT_RENAME: (
                        lambda context: (
                            _handle_rename_symbol()
                        )
                    ),
                    BuiltInCommandIds.EDIT_FORMAT_DOCUMENT: (
                        lambda context: (
                            editor_tabs_widget.format_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_TRIGGER_SUGGEST: (
                        lambda context: (
                            editor_tabs_widget.trigger_suggest_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_ADD_CURSOR_ABOVE: (
                        lambda context: (
                            editor_tabs_widget.add_cursor_above_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_ADD_CURSOR_BELOW: (
                        lambda context: (
                            editor_tabs_widget.add_cursor_below_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.VIEW_TOGGLE_SPLIT_EDITOR: (
                        lambda context: (
                            editor_tabs_widget.toggle_split_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.PROJECT_OPEN: (
                        create_project_open_handler(
                            project_explorer=project_explorer,
                            settings_service=(
                                resolved_settings_service
                            ),
                            project_file_path_holder=(
                                project_file_path_holder
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.PROJECT_CLOSE: (
                        create_project_close_handler(
                            project_explorer=project_explorer,
                            editor_tabs_widget=editor_tabs_widget,
                            project_file_path_holder=(
                                project_file_path_holder
                            ),
                        )
                    ),
                    BuiltInCommandIds.PROJECT_NEW: (
                        create_project_new_handler(
                            project_explorer=project_explorer,
                            settings_service=(
                                resolved_settings_service
                            ),
                            project_file_path_holder=(
                                project_file_path_holder
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
                            project_file_path_holder=(
                                project_file_path_holder
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
                            project_file_path_holder=(
                                project_file_path_holder
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
                    BuiltInCommandIds.DEBUG_START: (
                        create_debug_start_handler(
                            editor_tabs_widget=editor_tabs_widget,
                            project_explorer=project_explorer,
                            debug_controller=debug_controller,
                            compiler_profile_service=(
                                compiler_profile_service
                            ),
                            toolchain_service=(
                                gnucobol_toolchain_service
                            ),
                            symbol_table_holder=(
                                debug_symbol_table_holder
                            ),
                            output_widget=output_widget,
                            problems_widget=problems_widget,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.DEBUG_STOP: (
                        create_debug_stop_handler(
                            debug_controller=debug_controller,
                        )
                    ),
                    BuiltInCommandIds.DEBUG_CONTINUE: (
                        create_debug_continue_handler(
                            debug_controller=debug_controller,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.DEBUG_STEP_OVER: (
                        create_debug_step_over_handler(
                            debug_controller=debug_controller,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.DEBUG_STEP_INTO: (
                        create_debug_step_into_handler(
                            debug_controller=debug_controller,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.DEBUG_STEP_OUT: (
                        create_debug_step_out_handler(
                            debug_controller=debug_controller,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.APPLICATION_EXIT: (
                        lambda context: (
                            main_window_holder[0].close()
                        )
                    ),
                    BuiltInCommandIds.EDIT_UNDO: (
                        lambda context: (
                            editor_tabs_widget.undo_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_REDO: (
                        lambda context: (
                            editor_tabs_widget.redo_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_CUT: (
                        lambda context: (
                            editor_tabs_widget.cut_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_COPY: (
                        lambda context: (
                            editor_tabs_widget.copy_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_PASTE: (
                        lambda context: (
                            editor_tabs_widget.paste_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_DELETE: (
                        lambda context: (
                            editor_tabs_widget
                            .delete_selection_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_SELECT_ALL: (
                        lambda context: (
                            editor_tabs_widget
                            .select_all_on_active_tab()
                        )
                    ),
                    BuiltInCommandIds.EDIT_GO_TO: (
                        lambda context: (
                            _handle_go_to_line()
                        )
                    ),
                    BuiltInCommandIds.FILE_OPEN_RECENT: (
                        create_not_yet_available_handler(
                            "Open Recent File",
                            "There is no recent-files list yet -- "
                            "use File > Open Recent Project, or "
                            "File > Open.",
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.BUILD_CLEAN_PROJECT: (
                        create_clean_project_handler(
                            project_explorer=project_explorer,
                            output_widget=output_widget,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.BUILD_REBUILD_PROJECT: (
                        create_rebuild_project_handler(
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
                    BuiltInCommandIds.BUILD_RUN: (
                        create_not_yet_available_handler(
                            "Run",
                            "Running a compiled program outside the "
                            "debugger isn't implemented yet -- use "
                            "Debug > Start Debugging.",
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.BUILD_STOP: (
                        create_not_yet_available_handler(
                            "Stop",
                            "Running a compiled program outside the "
                            "debugger isn't implemented yet -- use "
                            "Debug > Stop Debugging.",
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.BUILD_VIEW_LISTING_FILE: (
                        create_view_listing_handler(
                            editor_tabs_widget=editor_tabs_widget,
                            project_explorer=project_explorer,
                            compiler_profile_service=(
                                compiler_profile_service
                            ),
                            toolchain_service=(
                                gnucobol_toolchain_service
                            ),
                            output_widget=output_widget,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_FETCH: (
                        create_fetch_handler(
                            git_service=git_service,
                            project_explorer=project_explorer,
                            git_changes_widget=git_changes_widget,
                            git_repository_widget=(
                                git_repository_widget
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_PULL: (
                        create_pull_handler(
                            git_service=git_service,
                            project_explorer=project_explorer,
                            git_changes_widget=git_changes_widget,
                            git_repository_widget=(
                                git_repository_widget
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_PUSH: (
                        create_push_handler(
                            git_service=git_service,
                            project_explorer=project_explorer,
                            git_changes_widget=git_changes_widget,
                            git_repository_widget=(
                                git_repository_widget
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_SYNC: (
                        create_sync_handler(
                            git_service=git_service,
                            project_explorer=project_explorer,
                            git_changes_widget=git_changes_widget,
                            git_repository_widget=(
                                git_repository_widget
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_CLONE_REPOSITORY: (
                        create_clone_repository_handler(
                            git_service=git_service,
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_CREATE_REPOSITORY: (
                        create_create_repository_handler(
                            git_service=git_service,
                            project_explorer=project_explorer,
                            git_changes_widget=git_changes_widget,
                            git_repository_widget=(
                                git_repository_widget
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_MANAGE_BRANCHES: (
                        create_manage_branches_handler(
                            git_repository_widget=(
                                git_repository_widget
                            ),
                            reveal_git_repository_panel=(
                                _reveal_git_repository_panel
                            ),
                        )
                    ),
                    BuiltInCommandIds.GIT_REPOSITORY_SETTINGS: (
                        create_not_yet_available_handler(
                            "Repository Settings",
                            "Per-repository Git settings aren't "
                            "implemented yet.",
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.ACCESSIBILITY_SETTINGS: (
                        create_not_yet_available_handler(
                            "Accessibility Settings",
                            "No accessibility profiles are "
                            "configured yet.",
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.TOOLS_PLUGINS: (
                        create_not_yet_available_handler(
                            "Plugins",
                            "The extension/plugin system isn't "
                            "implemented yet.",
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.HELP_DOCUMENTATION: (
                        create_not_yet_available_handler(
                            "Documentation",
                            "There is no user documentation yet.",
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.HELP_KEYBOARD_SHORTCUTS: (
                        create_show_keyboard_shortcuts_handler(
                            command_service_provider=(
                                lambda: command_service_holder[0]
                            ),
                            parent_widget_provider=(
                                lambda: main_window_holder[0]
                            ),
                        )
                    ),
                    BuiltInCommandIds.HELP_ABOUT: (
                        create_show_about_handler(
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
    _invalid_contribution_ids = (
        contribution_service.validate_contributions()
    )

    if _invalid_contribution_ids:
        raise RuntimeError(
            "Command contributions reference unregistered command "
            f"IDs: {', '.join(_invalid_contribution_ids)}."
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
            BuiltInToolWindowIds.BREAKPOINTS: (
                lambda: breakpoints_widget
            ),
            BuiltInToolWindowIds.CALL_STACK: (
                lambda: call_stack_widget
            ),
            BuiltInToolWindowIds.LOCALS: (
                lambda: locals_widget
            ),
            BuiltInToolWindowIds.WATCH: (
                lambda: watch_widget
            ),
            BuiltInToolWindowIds.THREADS: (
                lambda: threads_widget
            ),
            BuiltInToolWindowIds.REGISTERS: (
                lambda: registers_widget
            ),
            BuiltInToolWindowIds.MEMORY: (
                lambda: memory_widget
            ),
        },
        status_bar_service=status_bar_service,
        central_widget=editor_tabs_widget,
    )
    main_window_holder[0] = window

    def _refresh_task_list() -> None:
        """Rescan the open project for TODO/FIXME-style tasks.

        :returns: None. Clears the Task List panel if no project is
            open, otherwise repopulates it with the tasks found.
        """

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
        """Refresh everything derived from the project when it changes.

        Clears the Output and Problems panels on every project switch.
        Neither panel used to be wired to clear on a project switch —
        only `build_commands.py`'s own clear calls at the *start* of the
        next build ever touched them, so a closed or replaced project's
        stale build transcript and diagnostics stayed on screen until
        the next build happened to run. Find Results is cleared for the
        same reason: Task List already had an equivalent clear-on-switch
        hook, and Find Results was simply missing the one-line call,
        so it kept showing a closed/replaced project's stale search
        results indefinitely.

        :param changed_project: The newly-open project, or `None` if
            the project was closed.
        :returns: None. Refreshes the status bar, clears the
            Output/Problems/Find Results panels, re-points the Git
            Changes/Repository panels and terminal's working directory
            at the new project, rescans the Task List, and refreshes
            the welcome page's recent-projects list.
        """

        window.refresh_status_bar()

        output_widget.clear()
        problems_widget.clear_diagnostics()

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
        find_results_widget.clear_results()

    project_explorer.project_changed.connect(
        _on_project_changed,
    )

    def _handle_welcome_new_project() -> None:
        """Run the New Project command from the welcome page's button.

        :returns: None. Delegates to the `PROJECT_NEW` command handler.
        """

        command_service_holder[0].execute(
            BuiltInCommandIds.PROJECT_NEW,
        )

    def _handle_welcome_open_project() -> None:
        """Run the Open Project command from the welcome page's button.

        :returns: None. Delegates to the `PROJECT_OPEN` command handler.
        """

        command_service_holder[0].execute(
            BuiltInCommandIds.PROJECT_OPEN,
        )

    def _handle_welcome_open_recent_project(
        project_path: Path,
    ) -> None:
        """Open one project chosen from the welcome page's recent list.

        :param project_path: The path of the recent project file to
            open, as chosen on the welcome page.
        :returns: None. Delegates to the `PROJECT_OPEN_RECENT` command
            handler with `project_path` passed as its `"path"` context
            value.
        """

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
        """Open a Find Results entry at its exact source position.

        :param path: The file the activated result belongs to.
        :param line: The 1-based line of the match.
        :param column: The 1-based column of the match.
        :returns: None. Opens `path` in the editor and moves the
            cursor to `line`/`column`.
        """

        editor_tabs_widget.open_path_at_line(
            path,
            line,
            column,
        )

    find_results_widget.result_activated.connect(
        _handle_find_result_activated,
    )

    def _refresh_outline() -> None:
        """Rebuild the Outline panel from the active tab's structure.

        :returns: None. Replaces the Outline panel's contents with the
            active tab's current outline.
        """

        outline_widget.set_outline(
            editor_tabs_widget.current_outline(),
        )

    def _refresh_live_diagnostics() -> None:
        """Rebuild the Problems panel's live diagnostics from the active tab.

        :returns: None. Replaces the Problems panel's live diagnostics
            with the active tab's current diagnostics.
        """

        problems_widget.set_live_diagnostics(
            editor_tabs_widget.current_diagnostics(),
        )

    def _handle_active_document_changed() -> None:
        """React to the active tab changing by refreshing derived panels.

        :returns: None. Refreshes the Outline and Problems panels.
        """

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
        """Open a Task List entry at its exact source position.

        :param path: The file the activated task belongs to.
        :param line: The 1-based line of the task marker.
        :param column: The 1-based column of the task marker.
        :returns: None. Opens `path` in the editor and moves the
            cursor to `line`/`column`.
        """

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
        """Rebuild the Bookmarks panel from every open tab's bookmarks.

        :returns: None. Replaces the Bookmarks panel's contents with
            every bookmark currently set across open tabs.
        """

        bookmarks_widget.set_bookmarks(
            editor_tabs_widget.all_bookmarks(),
        )

    editor_tabs_widget.bookmarks_changed.connect(
        _refresh_bookmarks,
    )
    bookmarks_widget.entry_activated.connect(
        editor_tabs_widget.reveal_bookmark,
    )

    def _refresh_breakpoints() -> None:
        """Rebuild the Breakpoints panel from every open tab's breakpoints.

        :returns: None. Replaces the Breakpoints panel's contents with
            every breakpoint currently set across open tabs.
        """

        breakpoints_widget.set_breakpoints(
            editor_tabs_widget.all_breakpoints(),
        )

    editor_tabs_widget.breakpoints_changed.connect(
        _refresh_breakpoints,
    )
    breakpoints_widget.entry_activated.connect(
        editor_tabs_widget.reveal_breakpoint,
    )

    def _sync_debug_breakpoints() -> None:
        """Push the debugged tab's current breakpoints to GDB, if active.

        :returns: None. Does nothing if no debug session is active, or
            if the debugged document is not open in an editor tab;
            otherwise pushes that tab's current breakpoint lines to the
            debug session.
        """

        if (
            not debug_controller.is_active
            or debug_controller.document_id is None
        ):
            return

        editor = editor_tabs_widget.editor_for_document(
            debug_controller.document_id,
        )

        if editor is not None:
            debug_controller.sync_breakpoints(
                editor.breakpoint_lines,
            )

    editor_tabs_widget.breakpoints_changed.connect(
        _sync_debug_breakpoints,
    )

    def _refresh_watch_now() -> None:
        """Re-evaluate every watch expression against the active debug session.

        :returns: None. Clears the Watch panel if no debug session is
            active; otherwise repopulates it with each expression's
            freshly-evaluated value.
        """

        if not debug_controller.is_active:
            watch_widget.clear_watches()
            return

        watch_widget.set_watches(
            evaluate_watch_expressions(
                debug_controller,
                watch_widget.expressions(),
            )
        )

    watch_widget.expressions_changed.connect(
        _refresh_watch_now,
    )

    def _handle_memory_read_requested(
        address: str,
        length: int,
    ) -> None:
        """Read a memory range from the active debug session for the Memory panel.

        :param address: The starting address to read from, as entered
            in the Memory panel.
        :param length: The number of bytes to read.
        :returns: None. Does nothing if no debug session is active;
            otherwise populates the Memory panel with the bytes read,
            or shows a warning dialog if the read fails.
        """

        if not debug_controller.is_active:
            return

        try:
            memory_widget.set_memory(
                debug_controller.read_memory(
                    address,
                    length,
                ),
            )
        except DEBUG_SESSION_ERRORS as error:
            QMessageBox.warning(
                main_window_holder[0],
                "Memory",
                str(error),
            )

    memory_widget.read_requested.connect(
        _handle_memory_read_requested,
    )

    def _handle_call_stack_frame_activated(
        path: Path,
        line: int,
    ) -> None:
        """Open the source location for an activated Call Stack frame.

        :param path: The source file the activated frame points to.
        :param line: The 1-based line the activated frame points to.
        :returns: None. Opens `path` in the editor and moves the
            cursor to `line`.
        """

        editor_tabs_widget.open_path_at_line(
            path,
            line,
        )

    call_stack_widget.frame_activated.connect(
        _handle_call_stack_frame_activated,
    )

    def _clear_debug_panels() -> None:
        call_stack_widget.clear_frames()
        locals_widget.clear_variables()
        threads_widget.clear_threads()
        registers_widget.clear_registers()
        watch_widget.clear_watches()
        # Editor §DebugGUI-2: the Memory panel was never included here,
        # so it kept showing a dead session's stale hex dump even on
        # the one path (natural program exit) that already cleared
        # every other panel.
        memory_widget.clear_memory()

    # Editor §DebugGUI-1: `stop()` is the one place every
    # session-ending path (natural exit below, and the manual "Stop
    # Debugging" command in debug_commands.py) already funnels
    # through -- connecting the panel clear to its `session_ended`
    # signal here covers both, instead of only the exited-normally
    # branch below as before.
    debug_controller.session_ended.connect(
        _clear_debug_panels,
    )

    def _handle_debug_stopped(
        event: StoppedEvent,
    ) -> None:
        if event.reason in (
            StopReason.EXITED,
            StopReason.EXITED_NORMALLY,
        ):
            exit_detail = (
                f" (exit code {event.exit_code})"
                if event.exit_code is not None
                else ""
            )
            output_widget.append_line(
                "Debug session ended: "
                f"{event.reason.value}{exit_detail}.",
            )
            debug_controller.stop()
            return

        call_stack_widget.set_frames(
            debug_controller.stack_frames(),
        )
        threads_widget.set_threads(
            debug_controller.threads(),
        )
        registers_widget.set_registers(
            debug_controller.registers(),
        )

        symbol_table = debug_symbol_table_holder[0]

        if symbol_table is not None:
            locals_widget.set_variables(
                collect_local_variables(
                    debug_controller,
                    symbol_table,
                ),
            )

        watch_widget.set_watches(
            evaluate_watch_expressions(
                debug_controller,
                watch_widget.expressions(),
            )
        )

        if (
            event.frame is not None
            and event.frame.source_path is not None
        ):
            editor_tabs_widget.open_path_at_line(
                event.frame.source_path,
                event.frame.line or 1,
            )

    debug_controller.stopped.connect(
        _handle_debug_stopped,
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
    # The native platform style (e.g. "windowsvista"/"windows11" on
    # Windows) renders a lot of chrome -- the menu bar, dock-widget
    # separators, splitter handles -- straight from the OS theme engine
    # and largely ignores a custom QPalette for it. Fusion is Qt's own
    # cross-platform style and fully respects QPalette everywhere, which
    # is what actually makes a custom theme look consistent rather than
    # a mix of the real theme and unstyled native chrome.
    application.setStyle(
        "Fusion",
    )

    window = create_main_window()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(
        main(),
    )
