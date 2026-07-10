"""Built-in OpenCobol2 application commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from opencobol2.commands.models import (
    Command,
    CommandContext,
    CommandHandler,
    CommandState,
)
from opencobol2.commands.registry import (
    CommandRegistry,
)


class BuiltInCommandIds:
    """Stable identifiers for OpenCobol2 built-in commands."""

    FILE_NEW = "file.new"
    FILE_OPEN = "file.open"
    FILE_SAVE = "file.save"
    FILE_SAVE_AS = "file.save-as"
    FILE_CLOSE = "file.close"
    FILE_EXIT = "file.exit"

    EDIT_UNDO = "edit.undo"
    EDIT_REDO = "edit.redo"
    EDIT_CUT = "edit.cut"
    EDIT_COPY = "edit.copy"
    EDIT_PASTE = "edit.paste"
    EDIT_SELECT_ALL = "edit.select-all"

    VIEW_TOGGLE_FIXED_FORMAT_GUIDES = (
        "view.toggle-fixed-format-guides"
    )
    VIEW_TOGGLE_WHITESPACE = "view.toggle-whitespace"
    VIEW_TOGGLE_OUTPUT = "view.toggle-output"

    BUILD_COMPILE = "build.compile"
    BUILD_COMPILE_AND_RUN = "build.compile-and-run"

    GIT_STATUS = "git.status"
    GIT_COMMIT = "git.commit"
    GIT_PULL = "git.pull"
    GIT_PUSH = "git.push"

    TOOLS_SETTINGS = "tools.settings"

    HELP_DOCUMENTATION = "help.documentation"
    HELP_ABOUT = "help.about"


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class BuiltInCommandHandlers:
    """Injectable handlers for OpenCobol2 built-in commands."""

    file_new: CommandHandler
    file_open: CommandHandler
    file_save: CommandHandler
    file_save_as: CommandHandler
    file_close: CommandHandler
    file_exit: CommandHandler

    edit_undo: CommandHandler
    edit_redo: CommandHandler
    edit_cut: CommandHandler
    edit_copy: CommandHandler
    edit_paste: CommandHandler
    edit_select_all: CommandHandler

    view_toggle_fixed_format_guides: CommandHandler
    view_toggle_whitespace: CommandHandler
    view_toggle_output: CommandHandler

    build_compile: CommandHandler
    build_compile_and_run: CommandHandler

    git_status: CommandHandler
    git_commit: CommandHandler
    git_pull: CommandHandler
    git_push: CommandHandler

    tools_settings: CommandHandler

    help_documentation: CommandHandler
    help_about: CommandHandler

    def __post_init__(self) -> None:
        """Validate all built-in command handlers."""

        for field_name in self.__dataclass_fields__:
            handler = getattr(
                self,
                field_name,
            )

            if not callable(
                handler,
            ):
                raise TypeError(
                    "Built-in command handler must be callable: "
                    f"{field_name}."
                )


def create_no_op_builtin_command_handlers(
) -> BuiltInCommandHandlers:
    """Create placeholder handlers for command catalog bootstrap."""

    return BuiltInCommandHandlers(
        file_new=_no_op_handler,
        file_open=_no_op_handler,
        file_save=_no_op_handler,
        file_save_as=_no_op_handler,
        file_close=_no_op_handler,
        file_exit=_no_op_handler,
        edit_undo=_no_op_handler,
        edit_redo=_no_op_handler,
        edit_cut=_no_op_handler,
        edit_copy=_no_op_handler,
        edit_paste=_no_op_handler,
        edit_select_all=_no_op_handler,
        view_toggle_fixed_format_guides=_no_op_handler,
        view_toggle_whitespace=_no_op_handler,
        view_toggle_output=_no_op_handler,
        build_compile=_no_op_handler,
        build_compile_and_run=_no_op_handler,
        git_status=_no_op_handler,
        git_commit=_no_op_handler,
        git_pull=_no_op_handler,
        git_push=_no_op_handler,
        tools_settings=_no_op_handler,
        help_documentation=_no_op_handler,
        help_about=_no_op_handler,
    )


def create_builtin_command_registry(
    *,
    handlers: BuiltInCommandHandlers,
) -> CommandRegistry:
    """Create the registry containing OpenCobol2 built-in commands."""

    if not isinstance(
        handlers,
        BuiltInCommandHandlers,
    ):
        raise TypeError(
            "Built-in command handlers must be "
            "BuiltInCommandHandlers."
        )

    registry = CommandRegistry()

    commands = (
        Command(
            command_id=BuiltInCommandIds.FILE_NEW,
            title="New",
            description="Create a new document.",
            category="File",
            default_shortcuts=(
                "Ctrl+N",
            ),
            handler=handlers.file_new,
        ),
        Command(
            command_id=BuiltInCommandIds.FILE_OPEN,
            title="Open",
            description="Open an existing document.",
            category="File",
            default_shortcuts=(
                "Ctrl+O",
            ),
            handler=handlers.file_open,
        ),
        Command(
            command_id=BuiltInCommandIds.FILE_SAVE,
            title="Save",
            description="Save the active document.",
            category="File",
            default_shortcuts=(
                "Ctrl+S",
            ),
            handler=handlers.file_save,
            state_provider=_requires_active_document,
        ),
        Command(
            command_id=BuiltInCommandIds.FILE_SAVE_AS,
            title="Save As",
            description=(
                "Save the active document to a new location."
            ),
            category="File",
            default_shortcuts=(
                "Ctrl+Shift+S",
            ),
            handler=handlers.file_save_as,
            state_provider=_requires_active_document,
        ),
        Command(
            command_id=BuiltInCommandIds.FILE_CLOSE,
            title="Close",
            description="Close the active document.",
            category="File",
            default_shortcuts=(
                "Ctrl+W",
            ),
            handler=handlers.file_close,
            state_provider=_requires_active_document,
        ),
        Command(
            command_id=BuiltInCommandIds.FILE_EXIT,
            title="Exit",
            description="Exit OpenCobol2.",
            category="File",
            handler=handlers.file_exit,
        ),
        Command(
            command_id=BuiltInCommandIds.EDIT_UNDO,
            title="Undo",
            description="Undo the previous edit.",
            category="Edit",
            default_shortcuts=(
                "Ctrl+Z",
            ),
            handler=handlers.edit_undo,
            state_provider=_requires_editor,
        ),
        Command(
            command_id=BuiltInCommandIds.EDIT_REDO,
            title="Redo",
            description="Redo the previous undone edit.",
            category="Edit",
            default_shortcuts=(
                "Ctrl+Y",
            ),
            handler=handlers.edit_redo,
            state_provider=_requires_editor,
        ),
        Command(
            command_id=BuiltInCommandIds.EDIT_CUT,
            title="Cut",
            description="Cut the current selection.",
            category="Edit",
            default_shortcuts=(
                "Ctrl+X",
            ),
            handler=handlers.edit_cut,
            state_provider=_requires_editor,
        ),
        Command(
            command_id=BuiltInCommandIds.EDIT_COPY,
            title="Copy",
            description="Copy the current selection.",
            category="Edit",
            default_shortcuts=(
                "Ctrl+C",
            ),
            handler=handlers.edit_copy,
            state_provider=_requires_editor,
        ),
        Command(
            command_id=BuiltInCommandIds.EDIT_PASTE,
            title="Paste",
            description="Paste clipboard content.",
            category="Edit",
            default_shortcuts=(
                "Ctrl+V",
            ),
            handler=handlers.edit_paste,
            state_provider=_requires_editor,
        ),
        Command(
            command_id=BuiltInCommandIds.EDIT_SELECT_ALL,
            title="Select All",
            description="Select all editor content.",
            category="Edit",
            default_shortcuts=(
                "Ctrl+A",
            ),
            handler=handlers.edit_select_all,
            state_provider=_requires_editor,
        ),
        Command(
            command_id=(
                BuiltInCommandIds
                .VIEW_TOGGLE_FIXED_FORMAT_GUIDES
            ),
            title="Fixed-Format Guides",
            description=(
                "Show or hide COBOL fixed-format column guides."
            ),
            category="View",
            handler=(
                handlers.view_toggle_fixed_format_guides
            ),
            state_provider=_fixed_format_guides_state,
        ),
        Command(
            command_id=(
                BuiltInCommandIds.VIEW_TOGGLE_WHITESPACE
            ),
            title="Whitespace",
            description="Show or hide whitespace markers.",
            category="View",
            handler=handlers.view_toggle_whitespace,
            state_provider=_whitespace_state,
        ),
        Command(
            command_id=BuiltInCommandIds.VIEW_TOGGLE_OUTPUT,
            title="Output",
            description="Show or hide the output panel.",
            category="View",
            handler=handlers.view_toggle_output,
            state_provider=_output_panel_state,
        ),
        Command(
            command_id=BuiltInCommandIds.BUILD_COMPILE,
            title="Compile",
            description="Compile the active COBOL document.",
            category="Build",
            default_shortcuts=(
                "Ctrl+B",
            ),
            handler=handlers.build_compile,
            state_provider=_requires_active_document,
        ),
        Command(
            command_id=(
                BuiltInCommandIds.BUILD_COMPILE_AND_RUN
            ),
            title="Compile and Run",
            description=(
                "Compile and run the active COBOL document."
            ),
            category="Build",
            default_shortcuts=(
                "Ctrl+F5",
            ),
            handler=handlers.build_compile_and_run,
            state_provider=_requires_active_document,
        ),
        Command(
            command_id=BuiltInCommandIds.GIT_STATUS,
            title="Status",
            description="Show Git repository status.",
            category="Git",
            handler=handlers.git_status,
            state_provider=_requires_git_repository,
        ),
        Command(
            command_id=BuiltInCommandIds.GIT_COMMIT,
            title="Commit",
            description="Commit staged Git changes.",
            category="Git",
            handler=handlers.git_commit,
            state_provider=_requires_git_repository,
        ),
        Command(
            command_id=BuiltInCommandIds.GIT_PULL,
            title="Pull",
            description="Pull changes from the Git remote.",
            category="Git",
            handler=handlers.git_pull,
            state_provider=_requires_git_repository,
        ),
        Command(
            command_id=BuiltInCommandIds.GIT_PUSH,
            title="Push",
            description="Push changes to the Git remote.",
            category="Git",
            handler=handlers.git_push,
            state_provider=_requires_git_repository,
        ),
        Command(
            command_id=BuiltInCommandIds.TOOLS_SETTINGS,
            title="Settings",
            description="Open OpenCobol2 settings.",
            category="Tools",
            handler=handlers.tools_settings,
        ),
        Command(
            command_id=(
                BuiltInCommandIds.HELP_DOCUMENTATION
            ),
            title="Documentation",
            description="Open OpenCobol2 documentation.",
            category="Help",
            handler=handlers.help_documentation,
        ),
        Command(
            command_id=BuiltInCommandIds.HELP_ABOUT,
            title="About OpenCobol2",
            description="Show information about OpenCobol2.",
            category="Help",
            handler=handlers.help_about,
        ),
    )

    for command in commands:
        registry.register(
            command,
        )

    return registry


def _requires_active_document(
    context: CommandContext,
) -> CommandState:
    """Enable a command when an active document exists."""

    return CommandState(
        enabled=(
            context.get(
                "active_document",
            )
            is not None
        ),
    )


def _requires_editor(
    context: CommandContext,
) -> CommandState:
    """Enable a command when an editor exists."""

    return CommandState(
        enabled=(
            context.get(
                "editor",
            )
            is not None
        ),
    )


def _requires_git_repository(
    context: CommandContext,
) -> CommandState:
    """Enable a command when a Git repository is active."""

    return CommandState(
        enabled=(
            context.get(
                "git_repository",
            )
            is not None
        ),
    )


def _fixed_format_guides_state(
    context: CommandContext,
) -> CommandState:
    """Return fixed-format guide command state."""

    return CommandState(
        checked=bool(
            context.get(
                "fixed_format_guides_visible",
                False,
            )
        ),
    )


def _whitespace_state(
    context: CommandContext,
) -> CommandState:
    """Return whitespace marker command state."""

    return CommandState(
        checked=bool(
            context.get(
                "whitespace_visible",
                False,
            )
        ),
    )


def _output_panel_state(
    context: CommandContext,
) -> CommandState:
    """Return output panel command state."""

    return CommandState(
        checked=bool(
            context.get(
                "output_panel_visible",
                False,
            )
        ),
    )


def _no_op_handler(
    context: CommandContext,
) -> None:
    """Perform no action."""