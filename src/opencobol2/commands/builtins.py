"""Built-in OpenCobol2 IDE commands and standard command surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from opencobol2.accessibility import (
    AccessibilityProfile,
    AccessibilityProfileRegistry,
)
from opencobol2.commands.contribution_registry import (
    CommandContributionRegistry,
)
from opencobol2.commands.contributions import (
    CommandContribution,
    CommandSurfaceKind,
    DynamicMenuContribution,
    DynamicMenuItem,
    DynamicMenuProvider,
    SubmenuContribution,
)
from opencobol2.commands.models import (
    Command,
    CommandContext,
    CommandHandler,
    CommandState,
)
from opencobol2.commands.registry import CommandRegistry
from opencobol2.tool_windows import (
    BuiltInToolWindowIds,
    ToolWindowState,
)


class BuiltInCommandHandlerNotConfiguredError(RuntimeError):
    """Raised when a built-in command has no application handler."""


class BuiltInCommandIds:
    """Stable identifiers for built-in OpenCobol2 IDE commands."""

    FILE_NEW = "file.new"
    PROJECT_NEW = "project.new"
    FILE_OPEN = "file.open"
    PROJECT_OPEN = "project.open"
    FILE_OPEN_RECENT = "file.open-recent"
    PROJECT_OPEN_RECENT = "project.open-recent"
    FILE_SAVE = "file.save"
    FILE_SAVE_AS = "file.save-as"
    FILE_SAVE_ALL = "file.save-all"
    PROJECT_SAVE_AS = "project.save-as"
    FILE_CLOSE = "file.close"
    FILE_CLOSE_ALL = "file.close-all"
    PROJECT_CLOSE = "project.close"
    APPLICATION_EXIT = "application.exit"

    EDIT_UNDO = "edit.undo"
    EDIT_REDO = "edit.redo"
    EDIT_CUT = "edit.cut"
    EDIT_COPY = "edit.copy"
    EDIT_PASTE = "edit.paste"
    EDIT_DELETE = "edit.delete"
    EDIT_SELECT_ALL = "edit.select-all"
    EDIT_FIND = "edit.find"
    EDIT_REPLACE = "edit.replace"
    EDIT_FIND_IN_FILES = "edit.find-in-files"
    EDIT_GO_TO = "edit.go-to"
    EDIT_TOGGLE_BOOKMARK = "edit.toggle-bookmark"

    VIEW_COMMAND_PALETTE = "view.command-palette"
    VIEW_PROJECT_EXPLORER = "view.project-explorer"
    VIEW_OUTPUT = "view.output"
    VIEW_PROBLEMS = "view.problems"
    VIEW_FIND_RESULTS = "view.find-results"
    VIEW_TERMINAL = "view.terminal"
    VIEW_OUTLINE = "view.outline"
    VIEW_TASK_LIST = "view.task-list"
    VIEW_BOOKMARKS = "view.bookmarks"
    VIEW_GIT_CHANGES = "view.git-changes"
    VIEW_GIT_REPOSITORY = "view.git-repository"

    BUILD_PROJECT = "build.project"
    BUILD_REBUILD_PROJECT = "build.rebuild-project"
    BUILD_CLEAN_PROJECT = "build.clean-project"
    BUILD_RUN = "build.run"
    BUILD_STOP = "build.stop"

    GIT_CREATE_REPOSITORY = "git.create-repository"
    GIT_CLONE_REPOSITORY = "git.clone-repository"
    GIT_FETCH = "git.fetch"
    GIT_PULL = "git.pull"
    GIT_PUSH = "git.push"
    GIT_SYNC = "git.sync"
    GIT_MANAGE_BRANCHES = "git.manage-branches"
    GIT_REPOSITORY_SETTINGS = "git.repository-settings"

    TOOLS_SETTINGS = "tools.settings"
    TOOLS_COMPILER_PROFILES = "tools.compiler-profiles"
    TOOLS_PLUGINS = "tools.plugins"

    ACCESSIBILITY_SETTINGS = "accessibility.settings"
    ACCESSIBILITY_ACTIVATE_PROFILE = (
        "accessibility.activate-profile"
    )
    ACCESSIBILITY_CLEAR_ACTIVE_PROFILE = (
        "accessibility.clear-active-profile"
    )

    HELP_DOCUMENTATION = "help.documentation"
    HELP_KEYBOARD_SHORTCUTS = "help.keyboard-shortcuts"
    HELP_ABOUT = "help.about"


class BuiltInCommandSurfaceIds:
    """Stable identifiers for built-in OpenCobol2 command surfaces."""

    FILE = "file"
    FILE_NEW = "file.new"

    EDIT = "edit"
    VIEW = "view"
    BUILD = "build"
    GIT = "git"
    TOOLS = "tools"
    ACCESSIBILITY = "accessibility"
    HELP = "help"


class BuiltInMenuContributionIds:
    """Stable identifiers for built-in menu contributions."""

    FILE_NEW = "core.menu.file.new"
    FILE_OPEN_RECENT = "core.menu.file.open-recent"
    PROJECT_OPEN_RECENT = "core.menu.file.open-recent-project"

    ACCESSIBILITY_PROFILES = (
        "core.menu.accessibility.profiles"
    )


@runtime_checkable
class ToolWindowCommandService(Protocol):
    """Tool-window operations required by built-in view commands."""

    def get_state(
        self,
        tool_window_id: str,
    ) -> ToolWindowState:
        """Return current state for one tool window."""
        ...

    def activate(
        self,
        tool_window_id: str,
    ) -> ToolWindowState:
        """Show and activate one tool window."""
        ...


@runtime_checkable
class AccessibilityCommandService(Protocol):
    """Accessibility operations required by built-in commands."""

    @property
    def profile_registry(
        self,
    ) -> AccessibilityProfileRegistry:
        """Return the accessibility profile registry."""
        ...

    @property
    def active_profile_id(
        self,
    ) -> UUID | None:
        """Return the active accessibility profile identifier."""
        ...

    def activate_profile(
        self,
        profile_id: UUID,
    ) -> AccessibilityProfile:
        """Activate one accessibility profile."""
        ...

    def clear_active_profile(
        self,
    ) -> None:
        """Clear the current profile selection."""
        ...


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class BuiltInCommandHandlers:
    """Application handlers supplied for built-in IDE commands.

    Commands whose behavior is already owned by the shell or accessibility
    services are wired directly by the built-in catalog and do not use this
    mapping.
    """

    values: Mapping[str, CommandHandler]

    def __post_init__(self) -> None:
        """Copy and validate supplied command handlers."""

        if not isinstance(
            self.values,
            Mapping,
        ):
            raise TypeError(
                "Built-in command handlers must be a mapping."
            )

        handlers = dict(
            self.values,
        )

        for command_id, handler in handlers.items():
            if not isinstance(
                command_id,
                str,
            ):
                raise TypeError(
                    "Built-in command handler IDs must be strings."
                )

            normalized_command_id = command_id.strip()

            if not normalized_command_id:
                raise ValueError(
                    "Built-in command handler IDs must not be empty."
                )

            if normalized_command_id != command_id:
                raise ValueError(
                    "Built-in command handler IDs must already be "
                    "normalized."
                )

            if not callable(
                handler,
            ):
                raise TypeError(
                    "Built-in command handlers must be callable."
                )

        object.__setattr__(
            self,
            "values",
            MappingProxyType(
                handlers,
            ),
        )

    def get(
        self,
        command_id: str,
    ) -> CommandHandler | None:
        """Return a configured handler when one exists."""

        return self.values.get(
            command_id,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class _CommandMetadata:
    """Declarative metadata for one externally handled command."""

    command_id: str
    title: str
    description: str
    category: str
    default_shortcuts: tuple[str, ...] = ()


_EXTERNAL_COMMANDS = (
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_NEW,
        title="New File",
        description="Create a new source file.",
        category="File",
        default_shortcuts=("Ctrl+N",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.PROJECT_NEW,
        title="New Project",
        description="Create a new OpenCobol2 project.",
        category="File",
        default_shortcuts=("Ctrl+Shift+N",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_OPEN,
        title="Open File",
        description="Open a source file.",
        category="File",
        default_shortcuts=("Ctrl+O",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.PROJECT_OPEN,
        title="Open Project",
        description="Open an existing OpenCobol2 project.",
        category="File",
        default_shortcuts=("Ctrl+Shift+O",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_OPEN_RECENT,
        title="Open Recent File",
        description="Open a file from the recent-file history.",
        category="File",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.PROJECT_OPEN_RECENT,
        title="Open Recent Project",
        description="Open a project from the recent-project history.",
        category="File",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_SAVE,
        title="Save",
        description="Save the active document.",
        category="File",
        default_shortcuts=("Ctrl+S",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_SAVE_AS,
        title="Save As",
        description="Save the active document to a new location.",
        category="File",
        default_shortcuts=("Ctrl+Shift+S",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_SAVE_ALL,
        title="Save All",
        description="Save all modified documents.",
        category="File",
        default_shortcuts=("Ctrl+Alt+S",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.PROJECT_SAVE_AS,
        title="Save Project As",
        description="Save the current project to a new location.",
        category="File",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_CLOSE,
        title="Close File",
        description="Close the active document.",
        category="File",
        default_shortcuts=("Ctrl+W",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.FILE_CLOSE_ALL,
        title="Close All Files",
        description="Close all open documents.",
        category="File",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.PROJECT_CLOSE,
        title="Close Project",
        description="Close the current project.",
        category="File",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.APPLICATION_EXIT,
        title="Exit",
        description="Exit OpenCobol2.",
        category="File",
        default_shortcuts=("Alt+F4",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_UNDO,
        title="Undo",
        description="Undo the previous editing operation.",
        category="Edit",
        default_shortcuts=("Ctrl+Z",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_REDO,
        title="Redo",
        description="Redo the previous undone editing operation.",
        category="Edit",
        default_shortcuts=("Ctrl+Y",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_CUT,
        title="Cut",
        description="Cut the current selection.",
        category="Edit",
        default_shortcuts=("Ctrl+X",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_COPY,
        title="Copy",
        description="Copy the current selection.",
        category="Edit",
        default_shortcuts=("Ctrl+C",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_PASTE,
        title="Paste",
        description="Paste clipboard content.",
        category="Edit",
        default_shortcuts=("Ctrl+V",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_DELETE,
        title="Delete",
        description="Delete the current selection.",
        category="Edit",
        default_shortcuts=("Delete",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_SELECT_ALL,
        title="Select All",
        description="Select all content in the active editor.",
        category="Edit",
        default_shortcuts=("Ctrl+A",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_FIND,
        title="Find",
        description="Find text in the active document.",
        category="Edit",
        default_shortcuts=("Ctrl+F",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_REPLACE,
        title="Replace",
        description="Find and replace text in the active document.",
        category="Edit",
        default_shortcuts=("Ctrl+H",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_FIND_IN_FILES,
        title="Find in Files",
        description="Search across project and workspace files.",
        category="Edit",
        default_shortcuts=("Ctrl+Shift+F",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_GO_TO,
        title="Go To",
        description="Navigate to a location or symbol.",
        category="Edit",
        default_shortcuts=("Ctrl+G",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.EDIT_TOGGLE_BOOKMARK,
        title="Toggle Bookmark",
        description="Toggle a bookmark on the current line.",
        category="Edit",
        default_shortcuts=("Ctrl+F2",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.VIEW_COMMAND_PALETTE,
        title="Command Palette",
        description="Search and execute application commands.",
        category="View",
        default_shortcuts=("Ctrl+Shift+P",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.BUILD_PROJECT,
        title="Build Project",
        description="Build the current project.",
        category="Build",
        default_shortcuts=("Ctrl+Shift+B",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.BUILD_REBUILD_PROJECT,
        title="Rebuild Project",
        description="Clean and rebuild the current project.",
        category="Build",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.BUILD_CLEAN_PROJECT,
        title="Clean Project",
        description="Remove build output for the current project.",
        category="Build",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.BUILD_RUN,
        title="Run",
        description="Run the current project or active program.",
        category="Build",
        default_shortcuts=("Ctrl+F5",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.BUILD_STOP,
        title="Stop",
        description="Stop the active build or running program.",
        category="Build",
        default_shortcuts=("Shift+F5",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_CREATE_REPOSITORY,
        title="Create Git Repository",
        description="Initialize a Git repository.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_CLONE_REPOSITORY,
        title="Clone Repository",
        description="Clone a Git repository.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_FETCH,
        title="Fetch",
        description="Fetch repository updates from configured remotes.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_PULL,
        title="Pull",
        description="Pull changes into the current branch.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_PUSH,
        title="Push",
        description="Push local changes to the configured remote.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_SYNC,
        title="Sync",
        description="Synchronize the current repository.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_MANAGE_BRANCHES,
        title="Manage Branches",
        description="Browse and manage Git branches.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.GIT_REPOSITORY_SETTINGS,
        title="Repository Settings",
        description="Configure repository-specific Git settings.",
        category="Git",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.TOOLS_SETTINGS,
        title="Settings",
        description="Open OpenCobol2 application settings.",
        category="Tools",
        default_shortcuts=("Ctrl+,",),
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.TOOLS_COMPILER_PROFILES,
        title="Compiler Profiles",
        description="Configure COBOL compiler profiles.",
        category="Tools",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.TOOLS_PLUGINS,
        title="Plugins",
        description="Browse and manage OpenCobol2 plugins.",
        category="Tools",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.ACCESSIBILITY_SETTINGS,
        title="Accessibility Settings",
        description="Configure needs-based accessibility preferences.",
        category="Accessibility",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.HELP_DOCUMENTATION,
        title="Documentation",
        description="Open OpenCobol2 documentation.",
        category="Help",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.HELP_KEYBOARD_SHORTCUTS,
        title="Keyboard Shortcuts",
        description="Review configured keyboard shortcuts.",
        category="Help",
    ),
    _CommandMetadata(
        command_id=BuiltInCommandIds.HELP_ABOUT,
        title="About OpenCobol2",
        description="View OpenCobol2 product and version information.",
        category="Help",
    ),
)


_TOOL_WINDOW_COMMANDS = (
    (
        BuiltInCommandIds.VIEW_PROJECT_EXPLORER,
        "Project Explorer",
        "Show and focus Project Explorer.",
        BuiltInToolWindowIds.PROJECT_EXPLORER,
    ),
    (
        BuiltInCommandIds.VIEW_OUTPUT,
        "Output",
        "Show and focus the Output tool window.",
        BuiltInToolWindowIds.OUTPUT,
    ),
    (
        BuiltInCommandIds.VIEW_PROBLEMS,
        "Problems",
        "Show and focus the Problems tool window.",
        BuiltInToolWindowIds.PROBLEMS,
    ),
    (
        BuiltInCommandIds.VIEW_FIND_RESULTS,
        "Find Results",
        "Show and focus the Find Results tool window.",
        BuiltInToolWindowIds.FIND_RESULTS,
    ),
    (
        BuiltInCommandIds.VIEW_TERMINAL,
        "Terminal",
        "Show and focus the Terminal tool window.",
        BuiltInToolWindowIds.TERMINAL,
    ),
    (
        BuiltInCommandIds.VIEW_OUTLINE,
        "Outline",
        "Show and focus the Outline tool window.",
        BuiltInToolWindowIds.OUTLINE,
    ),
    (
        BuiltInCommandIds.VIEW_TASK_LIST,
        "Task List",
        "Show and focus the Task List tool window.",
        BuiltInToolWindowIds.TASK_LIST,
    ),
    (
        BuiltInCommandIds.VIEW_BOOKMARKS,
        "Bookmarks",
        "Show and focus the Bookmarks tool window.",
        BuiltInToolWindowIds.BOOKMARKS,
    ),
    (
        BuiltInCommandIds.VIEW_GIT_CHANGES,
        "Git Changes",
        "Show and focus the Git Changes tool window.",
        BuiltInToolWindowIds.GIT_CHANGES,
    ),
    (
        BuiltInCommandIds.VIEW_GIT_REPOSITORY,
        "Git Repository",
        "Show and focus the Git Repository tool window.",
        BuiltInToolWindowIds.GIT_REPOSITORY,
    ),
)


def create_builtin_command_registry(
    *,
    tool_window_service: ToolWindowCommandService,
    accessibility_service: AccessibilityCommandService,
    handlers: BuiltInCommandHandlers | None = None,
) -> CommandRegistry:
    """Create the built-in OpenCobol2 IDE command registry."""

    _validate_tool_window_service(
        tool_window_service,
    )
    _validate_accessibility_service(
        accessibility_service,
    )

    if (
        handlers is not None
        and not isinstance(
            handlers,
            BuiltInCommandHandlers,
        )
    ):
        raise TypeError(
            "Built-in command handlers must be "
            "BuiltInCommandHandlers or None."
        )

    configured_handlers = (
        BuiltInCommandHandlers(
            values={},
        )
        if handlers is None
        else handlers
    )

    registry = CommandRegistry()

    for metadata in _EXTERNAL_COMMANDS:
        registry.register(
            Command(
                command_id=metadata.command_id,
                title=metadata.title,
                handler=_resolve_external_handler(
                    configured_handlers,
                    metadata.command_id,
                ),
                description=metadata.description,
                category=metadata.category,
                default_shortcuts=metadata.default_shortcuts,
            )
        )

    for (
        command_id,
        title,
        description,
        tool_window_id,
    ) in _TOOL_WINDOW_COMMANDS:
        registry.register(
            Command(
                command_id=command_id,
                title=title,
                handler=_create_tool_window_handler(
                    tool_window_service,
                    tool_window_id,
                ),
                description=description,
                category="View",
                state_provider=_create_tool_window_state_provider(
                    tool_window_service,
                    tool_window_id,
                ),
            )
        )

    registry.register(
        Command(
            command_id=(
                BuiltInCommandIds.ACCESSIBILITY_ACTIVATE_PROFILE
            ),
            title="Activate Accessibility Profile",
            handler=_create_accessibility_profile_handler(
                accessibility_service,
            ),
            description=(
                "Activate a named accessibility and working-environment "
                "profile."
            ),
            category="Accessibility",
            state_provider=(
                _create_accessibility_profile_state_provider(
                    accessibility_service,
                )
            ),
        )
    )

    registry.register(
        Command(
            command_id=(
                BuiltInCommandIds.ACCESSIBILITY_CLEAR_ACTIVE_PROFILE
            ),
            title="Clear Active Accessibility Profile",
            handler=lambda context: (
                accessibility_service.clear_active_profile()
            ),
            description=(
                "Clear the active accessibility profile selection while "
                "preserving current accessibility settings."
            ),
            category="Accessibility",
            state_provider=lambda context: CommandState(
                enabled=(
                    accessibility_service.active_profile_id
                    is not None
                ),
            ),
        )
    )

    return registry


def create_builtin_command_contribution_registry(
    *,
    recent_file_provider: DynamicMenuProvider,
    recent_project_provider: DynamicMenuProvider,
    accessibility_service: AccessibilityCommandService,
) -> CommandContributionRegistry:
    """Create standard built-in IDE command surface declarations."""

    if not callable(
        recent_file_provider,
    ):
        raise TypeError(
            "Recent-file menu provider must be callable."
        )

    if not callable(
        recent_project_provider,
    ):
        raise TypeError(
            "Recent-project menu provider must be callable."
        )

    _validate_accessibility_service(
        accessibility_service,
    )

    registry = CommandContributionRegistry()

    _register_file_surface(
        registry,
        recent_file_provider=recent_file_provider,
        recent_project_provider=recent_project_provider,
    )
    _register_edit_surface(
        registry,
    )
    _register_view_surface(
        registry,
    )
    _register_build_surface(
        registry,
    )
    _register_git_surface(
        registry,
    )
    _register_tools_surface(
        registry,
    )
    _register_accessibility_surface(
        registry,
        accessibility_service=accessibility_service,
    )
    _register_help_surface(
        registry,
    )

    return registry


def _register_file_surface(
    registry: CommandContributionRegistry,
    *,
    recent_file_provider: DynamicMenuProvider,
    recent_project_provider: DynamicMenuProvider,
) -> None:
    """Register the standard File menu surface."""

    registry.register(
        SubmenuContribution(
            contribution_id=BuiltInMenuContributionIds.FILE_NEW,
            title="New",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id=BuiltInCommandSurfaceIds.FILE,
            submenu_id=BuiltInCommandSurfaceIds.FILE_NEW,
            group_id="new",
            group_order=10,
            order=10,
        )
    )

    _register_command_contribution(
        registry,
        "core.menu.file.open-file",
        BuiltInCommandIds.FILE_OPEN,
        BuiltInCommandSurfaceIds.FILE,
        "open",
        20,
        10,
    )
    _register_command_contribution(
        registry,
        "core.menu.file.open-project",
        BuiltInCommandIds.PROJECT_OPEN,
        BuiltInCommandSurfaceIds.FILE,
        "open",
        20,
        20,
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id=(
                BuiltInMenuContributionIds.FILE_OPEN_RECENT
            ),
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id=BuiltInCommandSurfaceIds.FILE,
            provider=recent_file_provider,
            group_id="open",
            group_order=20,
            order=30,
        )
    )
    registry.register(
        DynamicMenuContribution(
            contribution_id=(
                BuiltInMenuContributionIds.PROJECT_OPEN_RECENT
            ),
            title="Open Recent Project",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id=BuiltInCommandSurfaceIds.FILE,
            provider=recent_project_provider,
            group_id="open",
            group_order=20,
            order=40,
        )
    )

    _register_command_contribution(
        registry,
        "core.menu.file.save",
        BuiltInCommandIds.FILE_SAVE,
        BuiltInCommandSurfaceIds.FILE,
        "save",
        30,
        10,
        separator_before=True,
    )
    _register_command_contribution(
        registry,
        "core.menu.file.save-as",
        BuiltInCommandIds.FILE_SAVE_AS,
        BuiltInCommandSurfaceIds.FILE,
        "save",
        30,
        20,
    )
    _register_command_contribution(
        registry,
        "core.menu.file.save-all",
        BuiltInCommandIds.FILE_SAVE_ALL,
        BuiltInCommandSurfaceIds.FILE,
        "save",
        30,
        30,
    )
    _register_command_contribution(
        registry,
        "core.menu.file.save-project-as",
        BuiltInCommandIds.PROJECT_SAVE_AS,
        BuiltInCommandSurfaceIds.FILE,
        "save",
        30,
        40,
    )

    _register_command_contribution(
        registry,
        "core.menu.file.close-file",
        BuiltInCommandIds.FILE_CLOSE,
        BuiltInCommandSurfaceIds.FILE,
        "close",
        40,
        10,
        separator_before=True,
    )
    _register_command_contribution(
        registry,
        "core.menu.file.close-all",
        BuiltInCommandIds.FILE_CLOSE_ALL,
        BuiltInCommandSurfaceIds.FILE,
        "close",
        40,
        20,
    )
    _register_command_contribution(
        registry,
        "core.menu.file.close-project",
        BuiltInCommandIds.PROJECT_CLOSE,
        BuiltInCommandSurfaceIds.FILE,
        "close",
        40,
        30,
    )

    _register_command_contribution(
        registry,
        "core.menu.file.exit",
        BuiltInCommandIds.APPLICATION_EXIT,
        BuiltInCommandSurfaceIds.FILE,
        "application",
        50,
        10,
        separator_before=True,
    )

    _register_command_contribution(
        registry,
        "core.menu.file.new.file",
        BuiltInCommandIds.FILE_NEW,
        BuiltInCommandSurfaceIds.FILE_NEW,
        "new",
        10,
        10,
    )
    _register_command_contribution(
        registry,
        "core.menu.file.new.project",
        BuiltInCommandIds.PROJECT_NEW,
        BuiltInCommandSurfaceIds.FILE_NEW,
        "new",
        10,
        20,
    )


def _register_edit_surface(
    registry: CommandContributionRegistry,
) -> None:
    """Register the standard Edit menu surface."""

    _register_command_contribution(
        registry,
        "core.menu.edit.undo",
        BuiltInCommandIds.EDIT_UNDO,
        BuiltInCommandSurfaceIds.EDIT,
        "history",
        10,
        10,
    )
    _register_command_contribution(
        registry,
        "core.menu.edit.redo",
        BuiltInCommandIds.EDIT_REDO,
        BuiltInCommandSurfaceIds.EDIT,
        "history",
        10,
        20,
    )

    for order, (
        contribution_id,
        command_id,
    ) in enumerate(
        (
            (
                "core.menu.edit.cut",
                BuiltInCommandIds.EDIT_CUT,
            ),
            (
                "core.menu.edit.copy",
                BuiltInCommandIds.EDIT_COPY,
            ),
            (
                "core.menu.edit.paste",
                BuiltInCommandIds.EDIT_PASTE,
            ),
            (
                "core.menu.edit.delete",
                BuiltInCommandIds.EDIT_DELETE,
            ),
            (
                "core.menu.edit.select-all",
                BuiltInCommandIds.EDIT_SELECT_ALL,
            ),
        ),
        start=1,
    ):
        _register_command_contribution(
            registry,
            contribution_id,
            command_id,
            BuiltInCommandSurfaceIds.EDIT,
            "selection",
            20,
            order * 10,
            separator_before=(order == 1),
        )

    for order, (
        contribution_id,
        command_id,
    ) in enumerate(
        (
            (
                "core.menu.edit.find",
                BuiltInCommandIds.EDIT_FIND,
            ),
            (
                "core.menu.edit.replace",
                BuiltInCommandIds.EDIT_REPLACE,
            ),
            (
                "core.menu.edit.find-in-files",
                BuiltInCommandIds.EDIT_FIND_IN_FILES,
            ),
            (
                "core.menu.edit.go-to",
                BuiltInCommandIds.EDIT_GO_TO,
            ),
            (
                "core.menu.edit.toggle-bookmark",
                BuiltInCommandIds.EDIT_TOGGLE_BOOKMARK,
            ),
        ),
        start=1,
    ):
        _register_command_contribution(
            registry,
            contribution_id,
            command_id,
            BuiltInCommandSurfaceIds.EDIT,
            "navigation",
            30,
            order * 10,
            separator_before=(order == 1),
        )


def _register_view_surface(
    registry: CommandContributionRegistry,
) -> None:
    """Register the standard View menu surface."""

    _register_command_contribution(
        registry,
        "core.menu.view.command-palette",
        BuiltInCommandIds.VIEW_COMMAND_PALETTE,
        BuiltInCommandSurfaceIds.VIEW,
        "commands",
        10,
        10,
    )

    for order, (
        contribution_id,
        command_id,
    ) in enumerate(
        (
            (
                "core.menu.view.project-explorer",
                BuiltInCommandIds.VIEW_PROJECT_EXPLORER,
            ),
            (
                "core.menu.view.output",
                BuiltInCommandIds.VIEW_OUTPUT,
            ),
            (
                "core.menu.view.problems",
                BuiltInCommandIds.VIEW_PROBLEMS,
            ),
            (
                "core.menu.view.find-results",
                BuiltInCommandIds.VIEW_FIND_RESULTS,
            ),
            (
                "core.menu.view.terminal",
                BuiltInCommandIds.VIEW_TERMINAL,
            ),
            (
                "core.menu.view.outline",
                BuiltInCommandIds.VIEW_OUTLINE,
            ),
            (
                "core.menu.view.task-list",
                BuiltInCommandIds.VIEW_TASK_LIST,
            ),
            (
                "core.menu.view.bookmarks",
                BuiltInCommandIds.VIEW_BOOKMARKS,
            ),
            (
                "core.menu.view.git-changes",
                BuiltInCommandIds.VIEW_GIT_CHANGES,
            ),
            (
                "core.menu.view.git-repository",
                BuiltInCommandIds.VIEW_GIT_REPOSITORY,
            ),
        ),
        start=1,
    ):
        _register_command_contribution(
            registry,
            contribution_id,
            command_id,
            BuiltInCommandSurfaceIds.VIEW,
            "tool-windows",
            20,
            order * 10,
            separator_before=(order == 1),
        )


def _register_build_surface(
    registry: CommandContributionRegistry,
) -> None:
    """Register the standard Build menu surface."""

    for order, (
        contribution_id,
        command_id,
    ) in enumerate(
        (
            (
                "core.menu.build.project",
                BuiltInCommandIds.BUILD_PROJECT,
            ),
            (
                "core.menu.build.rebuild-project",
                BuiltInCommandIds.BUILD_REBUILD_PROJECT,
            ),
            (
                "core.menu.build.clean-project",
                BuiltInCommandIds.BUILD_CLEAN_PROJECT,
            ),
        ),
        start=1,
    ):
        _register_command_contribution(
            registry,
            contribution_id,
            command_id,
            BuiltInCommandSurfaceIds.BUILD,
            "build",
            10,
            order * 10,
        )

    _register_command_contribution(
        registry,
        "core.menu.build.run",
        BuiltInCommandIds.BUILD_RUN,
        BuiltInCommandSurfaceIds.BUILD,
        "execution",
        20,
        10,
        separator_before=True,
    )
    _register_command_contribution(
        registry,
        "core.menu.build.stop",
        BuiltInCommandIds.BUILD_STOP,
        BuiltInCommandSurfaceIds.BUILD,
        "execution",
        20,
        20,
    )


def _register_git_surface(
    registry: CommandContributionRegistry,
) -> None:
    """Register the concise top-level Git menu surface."""

    _register_command_contribution(
        registry,
        "core.menu.git.changes",
        BuiltInCommandIds.VIEW_GIT_CHANGES,
        BuiltInCommandSurfaceIds.GIT,
        "surfaces",
        10,
        10,
    )
    _register_command_contribution(
        registry,
        "core.menu.git.repository",
        BuiltInCommandIds.VIEW_GIT_REPOSITORY,
        BuiltInCommandSurfaceIds.GIT,
        "surfaces",
        10,
        20,
    )

    _register_command_contribution(
        registry,
        "core.menu.git.create-repository",
        BuiltInCommandIds.GIT_CREATE_REPOSITORY,
        BuiltInCommandSurfaceIds.GIT,
        "repository",
        20,
        10,
        separator_before=True,
    )
    _register_command_contribution(
        registry,
        "core.menu.git.clone-repository",
        BuiltInCommandIds.GIT_CLONE_REPOSITORY,
        BuiltInCommandSurfaceIds.GIT,
        "repository",
        20,
        20,
    )

    for order, (
        contribution_id,
        command_id,
    ) in enumerate(
        (
            (
                "core.menu.git.fetch",
                BuiltInCommandIds.GIT_FETCH,
            ),
            (
                "core.menu.git.pull",
                BuiltInCommandIds.GIT_PULL,
            ),
            (
                "core.menu.git.push",
                BuiltInCommandIds.GIT_PUSH,
            ),
            (
                "core.menu.git.sync",
                BuiltInCommandIds.GIT_SYNC,
            ),
        ),
        start=1,
    ):
        _register_command_contribution(
            registry,
            contribution_id,
            command_id,
            BuiltInCommandSurfaceIds.GIT,
            "synchronization",
            30,
            order * 10,
            separator_before=(order == 1),
        )

    _register_command_contribution(
        registry,
        "core.menu.git.manage-branches",
        BuiltInCommandIds.GIT_MANAGE_BRANCHES,
        BuiltInCommandSurfaceIds.GIT,
        "management",
        40,
        10,
        separator_before=True,
    )
    _register_command_contribution(
        registry,
        "core.menu.git.repository-settings",
        BuiltInCommandIds.GIT_REPOSITORY_SETTINGS,
        BuiltInCommandSurfaceIds.GIT,
        "management",
        40,
        20,
    )


def _register_tools_surface(
    registry: CommandContributionRegistry,
) -> None:
    """Register the standard Tools menu surface."""

    _register_command_contribution(
        registry,
        "core.menu.tools.compiler-profiles",
        BuiltInCommandIds.TOOLS_COMPILER_PROFILES,
        BuiltInCommandSurfaceIds.TOOLS,
        "configuration",
        10,
        10,
    )
    _register_command_contribution(
        registry,
        "core.menu.tools.plugins",
        BuiltInCommandIds.TOOLS_PLUGINS,
        BuiltInCommandSurfaceIds.TOOLS,
        "extensions",
        20,
        10,
        separator_before=True,
    )
    _register_command_contribution(
        registry,
        "core.menu.tools.settings",
        BuiltInCommandIds.TOOLS_SETTINGS,
        BuiltInCommandSurfaceIds.TOOLS,
        "settings",
        30,
        10,
        separator_before=True,
    )


def _register_accessibility_surface(
    registry: CommandContributionRegistry,
    *,
    accessibility_service: AccessibilityCommandService,
) -> None:
    """Register the first-class Accessibility menu surface."""

    _register_command_contribution(
        registry,
        "core.menu.accessibility.settings",
        BuiltInCommandIds.ACCESSIBILITY_SETTINGS,
        BuiltInCommandSurfaceIds.ACCESSIBILITY,
        "settings",
        10,
        10,
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id=(
                BuiltInMenuContributionIds.ACCESSIBILITY_PROFILES
            ),
            title="Profiles",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id=BuiltInCommandSurfaceIds.ACCESSIBILITY,
            provider=_create_accessibility_profile_menu_provider(
                accessibility_service,
            ),
            group_id="profiles",
            group_order=20,
            order=10,
            separator_before=True,
        )
    )

    _register_command_contribution(
        registry,
        "core.menu.accessibility.clear-profile",
        (
            BuiltInCommandIds.ACCESSIBILITY_CLEAR_ACTIVE_PROFILE
        ),
        BuiltInCommandSurfaceIds.ACCESSIBILITY,
        "profiles",
        20,
        20,
    )


def _register_help_surface(
    registry: CommandContributionRegistry,
) -> None:
    """Register the standard Help menu surface."""

    _register_command_contribution(
        registry,
        "core.menu.help.documentation",
        BuiltInCommandIds.HELP_DOCUMENTATION,
        BuiltInCommandSurfaceIds.HELP,
        "resources",
        10,
        10,
    )
    _register_command_contribution(
        registry,
        "core.menu.help.keyboard-shortcuts",
        BuiltInCommandIds.HELP_KEYBOARD_SHORTCUTS,
        BuiltInCommandSurfaceIds.HELP,
        "resources",
        10,
        20,
    )
    _register_command_contribution(
        registry,
        "core.menu.help.about",
        BuiltInCommandIds.HELP_ABOUT,
        BuiltInCommandSurfaceIds.HELP,
        "product",
        20,
        10,
        separator_before=True,
    )


def _register_command_contribution(
    registry: CommandContributionRegistry,
    contribution_id: str,
    command_id: str,
    surface_id: str,
    group_id: str,
    group_order: int,
    order: int,
    *,
    separator_before: bool = False,
    separator_after: bool = False,
) -> None:
    """Register one direct built-in menu contribution."""

    registry.register(
        CommandContribution(
            contribution_id=contribution_id,
            command_id=command_id,
            surface_kind=CommandSurfaceKind.MENU,
            surface_id=surface_id,
            group_id=group_id,
            group_order=group_order,
            order=order,
            separator_before=separator_before,
            separator_after=separator_after,
        )
    )


def _resolve_external_handler(
    handlers: BuiltInCommandHandlers,
    command_id: str,
) -> CommandHandler:
    """Resolve an application handler or create an explicit failure."""

    handler = handlers.get(
        command_id,
    )

    if handler is not None:
        return handler

    def unconfigured_handler(
        context: CommandContext,
    ) -> Any:
        raise BuiltInCommandHandlerNotConfiguredError(
            "Built-in command handler is not configured: "
            f"{command_id!r}."
        )

    return unconfigured_handler


def _create_tool_window_handler(
    service: ToolWindowCommandService,
    tool_window_id: str,
) -> CommandHandler:
    """Create a command handler that activates one tool window."""

    def activate_tool_window(
        context: CommandContext,
    ) -> ToolWindowState:
        return service.activate(
            tool_window_id,
        )

    return activate_tool_window


def _create_tool_window_state_provider(
    service: ToolWindowCommandService,
    tool_window_id: str,
):
    """Create checked state for one tool-window command."""

    def get_tool_window_state(
        context: CommandContext,
    ) -> CommandState:
        state = service.get_state(
            tool_window_id,
        )
        return CommandState(
            checked=state.visible,
        )

    return get_tool_window_state


def _create_accessibility_profile_handler(
    service: AccessibilityCommandService,
) -> CommandHandler:
    """Create the accessibility profile activation handler."""

    def activate_profile(
        context: CommandContext,
    ) -> AccessibilityProfile:
        profile_id = context.require(
            "profile_id",
        )

        if not isinstance(
            profile_id,
            UUID,
        ):
            raise TypeError(
                "Accessibility profile command context profile_id "
                "must be a UUID."
            )

        return service.activate_profile(
            profile_id,
        )

    return activate_profile


def _create_accessibility_profile_state_provider(
    service: AccessibilityCommandService,
):
    """Create state for dynamic accessibility profile commands."""

    def get_profile_state(
        context: CommandContext,
    ) -> CommandState:
        profile_id = context.get(
            "profile_id",
        )

        return CommandState(
            checked=(
                isinstance(
                    profile_id,
                    UUID,
                )
                and service.active_profile_id
                == profile_id
            ),
        )

    return get_profile_state


def _create_accessibility_profile_menu_provider(
    service: AccessibilityCommandService,
) -> DynamicMenuProvider:
    """Create the live accessibility profile menu provider."""

    def get_profile_items(
        context: CommandContext,
    ) -> tuple[DynamicMenuItem, ...]:
        return tuple(
            DynamicMenuItem(
                title=profile.name,
                command_id=(
                    BuiltInCommandIds.ACCESSIBILITY_ACTIVATE_PROFILE
                ),
                context=CommandContext(
                    values={
                        "profile_id": profile.profile_id,
                    },
                ),
            )
            for profile in service.profile_registry.profiles
        )

    return get_profile_items


def _validate_tool_window_service(
    service: ToolWindowCommandService,
) -> None:
    """Validate the tool-window service dependency."""

    if not isinstance(
        service,
        ToolWindowCommandService,
    ):
        raise TypeError(
            "Built-in command tool-window service must satisfy "
            "ToolWindowCommandService."
        )


def _validate_accessibility_service(
    service: AccessibilityCommandService,
) -> None:
    """Validate the accessibility service dependency."""

    if not isinstance(
        service,
        AccessibilityCommandService,
    ):
        raise TypeError(
            "Built-in command accessibility service must satisfy "
            "AccessibilityCommandService."
        )