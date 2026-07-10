"""Unit tests for the built-in OpenCobol2 IDE command catalog."""

from __future__ import annotations

from uuid import uuid4

import pytest

from opencobol2.accessibility import (
    AccessibilityProfile,
    AccessibilityProfileRegistry,
)
from opencobol2.commands import (
    BuiltInCommandHandlerNotConfiguredError,
    BuiltInCommandHandlers,
    BuiltInCommandIds,
    BuiltInCommandSurfaceIds,
    BuiltInMenuContributionIds,
    CommandContext,
    CommandSurfaceKind,
    DynamicMenuItem,
    ResolvedDynamicMenuContribution,
    create_builtin_command_contribution_registry,
    create_builtin_command_registry,
)
from opencobol2.services.accessibility import (
    AccessibilityService,
)
from opencobol2.services.commands import (
    CommandService,
)
from opencobol2.services.tool_windows import (
    ToolWindowService,
)
from opencobol2.tool_windows import (
    BuiltInToolWindowIds,
    create_builtin_tool_window_registry,
)


def _create_services() -> tuple[
    ToolWindowService,
    AccessibilityService,
]:
    """Create real shell and accessibility services."""

    tool_window_service = ToolWindowService(
        registry=create_builtin_tool_window_registry(),
    )
    accessibility_service = AccessibilityService(
        profile_registry=AccessibilityProfileRegistry(),
        tool_window_service=tool_window_service,
    )

    return (
        tool_window_service,
        accessibility_service,
    )


def _empty_recent_provider(
    context: CommandContext,
) -> tuple[DynamicMenuItem, ...]:
    """Return an empty recent-item menu."""

    return ()


def test_builtin_command_catalog_contains_real_ide_workflows() -> None:
    tool_windows, accessibility = _create_services()

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )

    expected_ids = {
        BuiltInCommandIds.FILE_NEW,
        BuiltInCommandIds.PROJECT_NEW,
        BuiltInCommandIds.FILE_OPEN,
        BuiltInCommandIds.PROJECT_OPEN,
        BuiltInCommandIds.FILE_OPEN_RECENT,
        BuiltInCommandIds.PROJECT_OPEN_RECENT,
        BuiltInCommandIds.FILE_SAVE,
        BuiltInCommandIds.FILE_SAVE_AS,
        BuiltInCommandIds.FILE_SAVE_ALL,
        BuiltInCommandIds.PROJECT_SAVE_AS,
        BuiltInCommandIds.FILE_CLOSE,
        BuiltInCommandIds.FILE_CLOSE_ALL,
        BuiltInCommandIds.PROJECT_CLOSE,
        BuiltInCommandIds.APPLICATION_EXIT,
        BuiltInCommandIds.VIEW_COMMAND_PALETTE,
        BuiltInCommandIds.VIEW_PROJECT_EXPLORER,
        BuiltInCommandIds.VIEW_OUTPUT,
        BuiltInCommandIds.VIEW_PROBLEMS,
        BuiltInCommandIds.VIEW_FIND_RESULTS,
        BuiltInCommandIds.VIEW_GIT_CHANGES,
        BuiltInCommandIds.VIEW_GIT_REPOSITORY,
        BuiltInCommandIds.BUILD_PROJECT,
        BuiltInCommandIds.BUILD_REBUILD_PROJECT,
        BuiltInCommandIds.BUILD_CLEAN_PROJECT,
        BuiltInCommandIds.BUILD_RUN,
        BuiltInCommandIds.BUILD_STOP,
        BuiltInCommandIds.GIT_CREATE_REPOSITORY,
        BuiltInCommandIds.GIT_CLONE_REPOSITORY,
        BuiltInCommandIds.GIT_FETCH,
        BuiltInCommandIds.GIT_PULL,
        BuiltInCommandIds.GIT_PUSH,
        BuiltInCommandIds.GIT_SYNC,
        BuiltInCommandIds.GIT_MANAGE_BRANCHES,
        BuiltInCommandIds.GIT_REPOSITORY_SETTINGS,
        BuiltInCommandIds.TOOLS_SETTINGS,
        BuiltInCommandIds.TOOLS_COMPILER_PROFILES,
        BuiltInCommandIds.TOOLS_PLUGINS,
        BuiltInCommandIds.ACCESSIBILITY_SETTINGS,
        BuiltInCommandIds.ACCESSIBILITY_ACTIVATE_PROFILE,
        BuiltInCommandIds.ACCESSIBILITY_CLEAR_ACTIVE_PROFILE,
        BuiltInCommandIds.HELP_DOCUMENTATION,
        BuiltInCommandIds.HELP_KEYBOARD_SHORTCUTS,
        BuiltInCommandIds.HELP_ABOUT,
    }

    registered_ids = {
        command.command_id
        for command in registry.commands
    }

    assert expected_ids <= registered_ids


def test_builtin_commands_expose_searchable_metadata() -> None:
    tool_windows, accessibility = _create_services()

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )

    for command in registry.commands:
        assert command.title
        assert command.description
        assert command.category


def test_unconfigured_application_command_fails_explicitly() -> None:
    tool_windows, accessibility = _create_services()

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )
    service = CommandService(
        registry=registry,
    )

    with pytest.raises(
        BuiltInCommandHandlerNotConfiguredError,
        match="file.save",
    ):
        service.execute(
            BuiltInCommandIds.FILE_SAVE,
        )


def test_supplied_application_handler_executes() -> None:
    tool_windows, accessibility = _create_services()
    executions: list[str] = []

    handlers = BuiltInCommandHandlers(
        values={
            BuiltInCommandIds.FILE_SAVE: (
                lambda context: executions.append(
                    "saved",
                )
            ),
        },
    )

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
        handlers=handlers,
    )
    service = CommandService(
        registry=registry,
    )

    service.execute(
        BuiltInCommandIds.FILE_SAVE,
    )

    assert executions == [
        "saved",
    ]


def test_view_tool_window_command_activates_real_tool_window() -> None:
    tool_windows, accessibility = _create_services()

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )
    service = CommandService(
        registry=registry,
    )

    initial_state = tool_windows.get_state(
        BuiltInToolWindowIds.GIT_CHANGES,
    )

    assert initial_state.visible is False
    assert initial_state.active is False

    service.execute(
        BuiltInCommandIds.VIEW_GIT_CHANGES,
    )

    active_state = tool_windows.get_state(
        BuiltInToolWindowIds.GIT_CHANGES,
    )

    assert active_state.visible is True
    assert active_state.active is True


def test_view_tool_window_command_is_checked_when_visible() -> None:
    tool_windows, accessibility = _create_services()

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )
    service = CommandService(
        registry=registry,
    )

    assert service.get_state(
        BuiltInCommandIds.VIEW_GIT_REPOSITORY,
    ).checked is False

    tool_windows.show(
        BuiltInToolWindowIds.GIT_REPOSITORY,
    )

    assert service.get_state(
        BuiltInCommandIds.VIEW_GIT_REPOSITORY,
    ).checked is True


def test_accessibility_profile_dynamic_menu_uses_stable_command() -> None:
    tool_windows, accessibility = _create_services()

    first = AccessibilityProfile(
        name="Focus Coding",
    )
    second = AccessibilityProfile(
        name="Laptop",
    )

    accessibility.profile_registry.register(
        first,
    )
    accessibility.profile_registry.register(
        second,
    )

    registry = create_builtin_command_contribution_registry(
        recent_file_provider=_empty_recent_provider,
        recent_project_provider=_empty_recent_provider,
        accessibility_service=accessibility,
    )

    contribution = registry.get(
        BuiltInMenuContributionIds.ACCESSIBILITY_PROFILES,
    )

    assert contribution.provider is not None

    items = tuple(
        contribution.provider(
            CommandContext(),
        ),
    )

    assert tuple(
        item.title
        for item in items
    ) == (
        "Focus Coding",
        "Laptop",
    )
    assert all(
        item.command_id
        == BuiltInCommandIds.ACCESSIBILITY_ACTIVATE_PROFILE
        for item in items
    )
    assert items[0].context.require(
        "profile_id",
    ) == first.profile_id
    assert items[1].context.require(
        "profile_id",
    ) == second.profile_id


def test_accessibility_profile_command_activates_profile() -> None:
    tool_windows, accessibility = _create_services()

    profile = AccessibilityProfile(
        name="Focus Coding",
    )
    accessibility.profile_registry.register(
        profile,
    )

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )
    service = CommandService(
        registry=registry,
    )

    service.execute(
        BuiltInCommandIds.ACCESSIBILITY_ACTIVATE_PROFILE,
        CommandContext(
            values={
                "profile_id": profile.profile_id,
            },
        ),
    )

    assert accessibility.active_profile_id == profile.profile_id

    state = service.get_state(
        BuiltInCommandIds.ACCESSIBILITY_ACTIVATE_PROFILE,
        CommandContext(
            values={
                "profile_id": profile.profile_id,
            },
        ),
    )

    assert state.checked is True


def test_clear_accessibility_profile_command_tracks_live_state() -> None:
    tool_windows, accessibility = _create_services()

    profile = AccessibilityProfile(
        name="Focus Coding",
    )
    accessibility.profile_registry.register(
        profile,
    )

    registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )
    service = CommandService(
        registry=registry,
    )

    assert service.get_state(
        BuiltInCommandIds.ACCESSIBILITY_CLEAR_ACTIVE_PROFILE,
    ).enabled is False

    accessibility.activate_profile(
        profile.profile_id,
    )

    assert service.get_state(
        BuiltInCommandIds.ACCESSIBILITY_CLEAR_ACTIVE_PROFILE,
    ).enabled is True

    service.execute(
        BuiltInCommandIds.ACCESSIBILITY_CLEAR_ACTIVE_PROFILE,
    )

    assert accessibility.active_profile_id is None
    assert service.get_state(
        BuiltInCommandIds.ACCESSIBILITY_CLEAR_ACTIVE_PROFILE,
    ).enabled is False


def test_file_surface_contains_static_and_dynamic_ide_workflows() -> None:
    _, accessibility = _create_services()

    registry = create_builtin_command_contribution_registry(
        recent_file_provider=_empty_recent_provider,
        recent_project_provider=_empty_recent_provider,
        accessibility_service=accessibility,
    )

    contributions = registry.for_surface(
        CommandSurfaceKind.MENU,
        BuiltInCommandSurfaceIds.FILE,
    )

    contribution_ids = tuple(
        contribution.contribution_id
        for contribution in contributions
    )

    assert contribution_ids[:5] == (
        BuiltInMenuContributionIds.FILE_NEW,
        "core.menu.file.open-file",
        "core.menu.file.open-project",
        BuiltInMenuContributionIds.FILE_OPEN_RECENT,
        BuiltInMenuContributionIds.PROJECT_OPEN_RECENT,
    )


def test_file_new_submenu_contains_file_and_project_commands() -> None:
    _, accessibility = _create_services()

    registry = create_builtin_command_contribution_registry(
        recent_file_provider=_empty_recent_provider,
        recent_project_provider=_empty_recent_provider,
        accessibility_service=accessibility,
    )

    contributions = registry.for_surface(
        CommandSurfaceKind.MENU,
        BuiltInCommandSurfaceIds.FILE_NEW,
    )

    assert tuple(
        contribution.command_id
        for contribution in contributions
    ) == (
        BuiltInCommandIds.FILE_NEW,
        BuiltInCommandIds.PROJECT_NEW,
    )


def test_git_menu_focuses_real_git_surfaces_before_operations() -> None:
    _, accessibility = _create_services()

    registry = create_builtin_command_contribution_registry(
        recent_file_provider=_empty_recent_provider,
        recent_project_provider=_empty_recent_provider,
        accessibility_service=accessibility,
    )

    contributions = registry.for_surface(
        CommandSurfaceKind.MENU,
        BuiltInCommandSurfaceIds.GIT,
    )

    assert tuple(
        contribution.command_id
        for contribution in contributions[:2]
    ) == (
        BuiltInCommandIds.VIEW_GIT_CHANGES,
        BuiltInCommandIds.VIEW_GIT_REPOSITORY,
    )


def test_duplicate_accessibility_profile_names_remain_distinct_items() -> None:
    tool_windows, accessibility = _create_services()

    first = AccessibilityProfile(
        name="Focus Coding",
        profile_id=uuid4(),
    )
    second = AccessibilityProfile(
        name="Focus Coding",
        profile_id=uuid4(),
    )

    accessibility.profile_registry.register(
        first,
    )
    accessibility.profile_registry.register(
        second,
    )

    command_registry = create_builtin_command_registry(
        tool_window_service=tool_windows,
        accessibility_service=accessibility,
    )
    contribution_registry = (
        create_builtin_command_contribution_registry(
            recent_file_provider=_empty_recent_provider,
            recent_project_provider=_empty_recent_provider,
            accessibility_service=accessibility,
        )
    )

    contribution = contribution_registry.get(
        BuiltInMenuContributionIds.ACCESSIBILITY_PROFILES,
    )
    items = tuple(
        contribution.provider(
            CommandContext(),
        ),
    )

    assert items[0].title == items[1].title
    assert (
        items[0].context.require(
            "profile_id",
        )
        != items[1].context.require(
            "profile_id",
        )
    )

    service = CommandService(
        registry=command_registry,
    )

    service.execute(
        items[1].command_id,
        items[1].context,
    )

    assert accessibility.active_profile_id == second.profile_id