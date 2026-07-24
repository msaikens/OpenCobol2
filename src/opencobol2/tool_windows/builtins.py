"""Built-in OpenCobol2 IDE tool windows."""

from __future__ import annotations

from opencobol2.tool_windows.models import (
    ToolWindowArea,
    ToolWindowDefinition,
)
from opencobol2.tool_windows.registry import (
    ToolWindowRegistry,
)


class BuiltInToolWindowIds:
    """Stable identifiers for built-in IDE tool windows."""

    PROJECT_EXPLORER = "project-explorer"
    OUTPUT = "output"
    PROBLEMS = "problems"
    FIND_RESULTS = "find-results"
    TERMINAL = "terminal"
    OUTLINE = "outline"
    TASK_LIST = "task-list"
    BOOKMARKS = "bookmarks"
    BREAKPOINTS = "breakpoints"
    GIT_CHANGES = "git-changes"
    GIT_REPOSITORY = "git-repository"
    CALL_STACK = "call-stack"
    LOCALS = "locals"
    WATCH = "watch"
    THREADS = "threads"
    REGISTERS = "registers"
    MEMORY = "memory"


def create_builtin_tool_window_registry(
) -> ToolWindowRegistry:
    """Create the built-in OpenCobol2 tool-window registry."""

    registry = ToolWindowRegistry()

    definitions = (
        ToolWindowDefinition(
            tool_window_id=(
                BuiltInToolWindowIds.PROJECT_EXPLORER
            ),
            title="Project Explorer",
            default_area=ToolWindowArea.LEFT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=True,
            default_pinned=True,
            accessibility_description=(
                "Browse projects, folders, source files, "
                "and project resources."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.OUTPUT,
            title="Output",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=True,
            default_pinned=False,
            accessibility_description=(
                "View compiler, build, and application output."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.PROBLEMS,
            title="Problems",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=True,
            default_pinned=False,
            accessibility_description=(
                "Review compiler diagnostics, warnings, "
                "and errors."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.FIND_RESULTS,
            title="Find Results",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "Review results from searches across files."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.TERMINAL,
            title="Terminal",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "Run shell commands and view their output."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.OUTLINE,
            title="Outline",
            default_area=ToolWindowArea.RIGHT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "Browse the active document's divisions, "
                "sections, and paragraphs."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.TASK_LIST,
            title="Task List",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "List TODO and FIXME comments across the "
                "open project."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.BOOKMARKS,
            title="Bookmarks",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "List bookmarked lines across open documents."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.BREAKPOINTS,
            title="Breakpoints",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "List breakpointed lines across open documents."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.GIT_CHANGES,
            title="Git Changes",
            default_area=ToolWindowArea.RIGHT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=True,
            accessibility_description=(
                "Review repository changes, stage files, "
                "and create commits."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=(
                BuiltInToolWindowIds.GIT_REPOSITORY
            ),
            title="Git Repository",
            default_area=ToolWindowArea.RIGHT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=True,
            accessibility_description=(
                "Browse Git branches, remotes, history, "
                "and repository structure."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.CALL_STACK,
            title="Call Stack",
            default_area=ToolWindowArea.RIGHT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "View the active debug session's call stack."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.LOCALS,
            title="Locals",
            default_area=ToolWindowArea.RIGHT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "View local COBOL variable values at the current "
                "debug stop."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.WATCH,
            title="Watch",
            default_area=ToolWindowArea.RIGHT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "Track custom expressions across a debug session."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.THREADS,
            title="Threads",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "View every thread in the debugged process."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.REGISTERS,
            title="Registers",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "View CPU register values at the current debug stop."
            ),
        ),
        ToolWindowDefinition(
            tool_window_id=BuiltInToolWindowIds.MEMORY,
            title="Memory",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.TOP,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=False,
            accessibility_description=(
                "Inspect raw memory at an address in the debugged "
                "process."
            ),
        ),
    )

    for definition in definitions:
        registry.register(
            definition,
        )

    return registry