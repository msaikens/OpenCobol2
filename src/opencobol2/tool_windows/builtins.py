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
    GIT_CHANGES = "git-changes"
    GIT_REPOSITORY = "git-repository"


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
    )

    for definition in definitions:
        registry.register(
            definition,
        )

    return registry