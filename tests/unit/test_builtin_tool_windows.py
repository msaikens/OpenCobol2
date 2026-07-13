"""Unit tests for built-in OpenCobol2 IDE tool windows."""

from __future__ import annotations

from opencobol2.tool_windows import (
    BuiltInToolWindowIds,
    ToolWindowArea,
    create_builtin_tool_window_registry,
)


def test_builtin_registry_contains_standard_tool_windows() -> None:
    registry = create_builtin_tool_window_registry()

    assert tuple(
        definition.tool_window_id
        for definition in registry.definitions
    ) == (
        BuiltInToolWindowIds.PROJECT_EXPLORER,
        BuiltInToolWindowIds.OUTPUT,
        BuiltInToolWindowIds.PROBLEMS,
        BuiltInToolWindowIds.FIND_RESULTS,
        BuiltInToolWindowIds.TERMINAL,
        BuiltInToolWindowIds.OUTLINE,
        BuiltInToolWindowIds.TASK_LIST,
        BuiltInToolWindowIds.BOOKMARKS,
        BuiltInToolWindowIds.BREAKPOINTS,
        BuiltInToolWindowIds.GIT_CHANGES,
        BuiltInToolWindowIds.GIT_REPOSITORY,
    )


def test_project_explorer_is_visible_and_pinned_by_default() -> None:
    registry = create_builtin_tool_window_registry()

    definition = registry.get(
        BuiltInToolWindowIds.PROJECT_EXPLORER,
    )

    assert definition.default_area is ToolWindowArea.LEFT
    assert definition.default_visible is True
    assert definition.default_pinned is True


def test_output_defaults_to_bottom_auto_hide() -> None:
    registry = create_builtin_tool_window_registry()

    definition = registry.get(
        BuiltInToolWindowIds.OUTPUT,
    )

    assert definition.default_area is ToolWindowArea.BOTTOM
    assert definition.default_visible is True
    assert definition.default_pinned is False


def test_git_changes_defaults_to_right_and_hidden() -> None:
    registry = create_builtin_tool_window_registry()

    definition = registry.get(
        BuiltInToolWindowIds.GIT_CHANGES,
    )

    assert definition.default_area is ToolWindowArea.RIGHT
    assert definition.default_visible is False
    assert definition.default_pinned is True


def test_builtin_tool_windows_expose_accessibility_metadata() -> None:
    registry = create_builtin_tool_window_registry()

    for definition in registry.definitions:
        assert definition.accessibility_name
        assert definition.accessibility_description