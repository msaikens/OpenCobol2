"""Tests for static and dynamic command surface contributions."""

from __future__ import annotations

from typing import Any

import pytest

from opencobol2.commands import (
    Command,
    CommandContext,
    CommandContribution,
    CommandContributionAlreadyRegisteredError,
    CommandContributionRegistry,
    CommandRegistry,
    CommandState,
    CommandSurfaceKind,
    DynamicMenuContribution,
    DynamicMenuItem,
    ResolvedCommandContribution,
    ResolvedDynamicMenuContribution,
    ResolvedSubmenuContribution,
    SubmenuContribution,
)
from opencobol2.services.command_contributions import (
    CommandContributionService,
)
from opencobol2.services.commands import (
    CommandDisabledError,
    CommandService,
)


def _create_service(
    *,
    commands: tuple[Command, ...] = (),
) -> tuple[
    CommandContributionRegistry,
    CommandContributionService,
]:
    """Create command contribution services for submenu tests."""

    command_registry = CommandRegistry()

    for command in commands:
        command_registry.register(
            command,
        )

    contribution_registry = CommandContributionRegistry()
    command_service = CommandService(
        registry=command_registry,
    )

    return (
        contribution_registry,
        CommandContributionService(
            command_service=command_service,
            contribution_registry=contribution_registry,
        ),
    )


def test_submenu_contribution_normalizes_metadata() -> None:
    contribution = SubmenuContribution(
        contribution_id=" core.menu.file.new ",
        title=" New ",
        surface_kind=CommandSurfaceKind.MENU,
        surface_id=" file ",
        submenu_id=" file.new ",
        group_id=" new ",
    )

    assert contribution.contribution_id == "core.menu.file.new"
    assert contribution.title == "New"
    assert contribution.surface_id == "file"
    assert contribution.submenu_id == "file.new"
    assert contribution.group_id == "new"


def test_dynamic_menu_contribution_normalizes_metadata() -> None:
    contribution = DynamicMenuContribution(
        contribution_id=" core.menu.file.recent ",
        title=" Open Recent ",
        surface_kind=CommandSurfaceKind.MENU,
        surface_id=" file ",
        group_id=" open ",
        provider=lambda context: (),
    )

    assert contribution.contribution_id == "core.menu.file.recent"
    assert contribution.title == "Open Recent"
    assert contribution.surface_id == "file"
    assert contribution.group_id == "open"


def test_dynamic_menu_item_normalizes_metadata() -> None:
    item = DynamicMenuItem(
        title=" PAYROLL.cob ",
        command_id=" file.open-recent ",
        secondary_text=" C:\\source\\PAYROLL.cob ",
    )

    assert item.title == "PAYROLL.cob"
    assert item.command_id == "file.open-recent"
    assert item.secondary_text == r"C:\source\PAYROLL.cob"


@pytest.mark.parametrize(
    "contribution_type",
    [
        SubmenuContribution,
        DynamicMenuContribution,
    ],
)
@pytest.mark.parametrize(
    "field_name",
    [
        "group_order",
        "order",
    ],
)
def test_menu_contribution_order_values_must_be_integers(
    contribution_type: type[
        SubmenuContribution
        | DynamicMenuContribution
    ],
    field_name: str,
) -> None:
    values: dict[str, Any] = {
        "contribution_id": "core.menu.file.test",
        "title": "Test",
        "surface_kind": CommandSurfaceKind.MENU,
        "surface_id": "file",
        field_name: True,
    }

    if contribution_type is SubmenuContribution:
        values["submenu_id"] = "file.test"
    else:
        values["provider"] = lambda context: ()

    with pytest.raises(
        TypeError,
        match="must be an integer",
    ):
        contribution_type(
            **values,
        )


def test_registry_orders_mixed_contribution_types_together() -> None:
    registry = CommandContributionRegistry()

    registry.register(
        CommandContribution(
            contribution_id="file.save",
            command_id="file.save",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="documents",
            group_order=20,
            order=10,
        )
    )
    registry.register(
        SubmenuContribution(
            contribution_id="file.new-menu",
            title="New",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            submenu_id="file.new",
            group_id="open",
            group_order=10,
            order=20,
        )
    )
    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (),
            group_order=10,
            order=10,
        )
    )

    contributions = registry.for_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert tuple(
        contribution.contribution_id
        for contribution in contributions
    ) == (
        "file.open-recent-menu",
        "file.new-menu",
        "file.save",
    )


def test_registry_preserves_registration_order_for_mixed_exact_ties() -> None:
    registry = CommandContributionRegistry()

    first = SubmenuContribution(
        contribution_id="first",
        title="First",
        surface_kind=CommandSurfaceKind.MENU,
        surface_id="file",
        submenu_id="first-menu",
        group_id="group-a",
        group_order=10,
        order=10,
    )
    second = DynamicMenuContribution(
        contribution_id="second",
        title="Second",
        surface_kind=CommandSurfaceKind.MENU,
        surface_id="file",
        group_id="group-b",
        provider=lambda context: (),
        group_order=10,
        order=10,
    )

    registry.register(
        first,
    )
    registry.register(
        second,
    )

    assert registry.for_surface(
        CommandSurfaceKind.MENU,
        "file",
    ) == (
        first,
        second,
    )


def test_registry_rejects_duplicate_ids_across_contribution_types() -> None:
    registry = CommandContributionRegistry()

    registry.register(
        SubmenuContribution(
            contribution_id="file.recent",
            title="Open Recent",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            submenu_id="file.recent",
            group_id="open",
        )
    )

    with pytest.raises(
        CommandContributionAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(
            DynamicMenuContribution(
                contribution_id="file.recent",
                title="Recent Files",
                surface_kind=CommandSurfaceKind.MENU,
                surface_id="file",
                group_id="open",
                provider=lambda context: (),
            )
        )


def test_static_submenu_resolves_as_container() -> None:
    registry, service = _create_service()

    registry.register(
        SubmenuContribution(
            contribution_id="file.new-menu",
            title="New",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            submenu_id="file.new",
            group_id="new",
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert len(resolved) == 1
    assert isinstance(
        resolved[0],
        ResolvedSubmenuContribution,
    )
    assert (
        resolved[0].contribution.submenu_id
        == "file.new"
    )


def test_static_submenu_children_use_existing_surface_resolution() -> None:
    command = Command(
        command_id="file.new-file",
        title="New File",
        handler=lambda context: None,
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        SubmenuContribution(
            contribution_id="file.new-menu",
            title="New",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            submenu_id="file.new",
            group_id="new",
        )
    )
    registry.register(
        CommandContribution(
            contribution_id="file.new-file",
            command_id="file.new-file",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file.new",
            group_id="files",
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file.new",
    )

    assert len(resolved) == 1
    assert isinstance(
        resolved[0],
        ResolvedCommandContribution,
    )
    assert (
        resolved[0].command.command_id
        == "file.new-file"
    )


def test_dynamic_menu_provider_receives_live_surface_context() -> None:
    received_context: list[CommandContext] = []

    def provider(
        context: CommandContext,
    ) -> tuple[DynamicMenuItem, ...]:
        received_context.append(
            context,
        )
        return ()

    registry, service = _create_service()

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=provider,
        )
    )

    context = CommandContext(
        values={
            "workspace_id": "workspace-1",
        },
    )

    service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
        context,
    )

    assert received_context == [
        context,
    ]


def test_dynamic_menu_resolves_items_against_item_context() -> None:
    command = Command(
        command_id="file.open-recent",
        title="Open Recent File",
        handler=lambda context: context.require(
            "path",
        ),
        state_provider=lambda context: CommandState(
            enabled=(
                context.get(
                    "path",
                )
                != "locked.cob"
            ),
        ),
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (
                DynamicMenuItem(
                    title="PAYROLL.cob",
                    command_id="file.open-recent",
                    context=CommandContext(
                        values={
                            "path": "PAYROLL.cob",
                        },
                    ),
                ),
                DynamicMenuItem(
                    title="LOCKED.cob",
                    command_id="file.open-recent",
                    context=CommandContext(
                        values={
                            "path": "locked.cob",
                        },
                    ),
                ),
            ),
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert len(resolved) == 1
    assert isinstance(
        resolved[0],
        ResolvedDynamicMenuContribution,
    )

    items = resolved[0].items

    assert len(items) == 2
    assert items[0].state.enabled is True
    assert items[1].state.enabled is False


def test_dynamic_item_false_additionally_disables_item() -> None:
    command = Command(
        command_id="project.open-recent",
        title="Open Recent Project",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            enabled=True,
        ),
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id="project.open-recent-menu",
            title="Open Recent Project",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (
                DynamicMenuItem(
                    title="BillingSystem",
                    command_id="project.open-recent",
                    enabled=False,
                ),
            ),
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert isinstance(
        resolved[0],
        ResolvedDynamicMenuContribution,
    )
    assert (
        resolved[0].items[0].state.enabled
        is False
    )


def test_dynamic_item_true_does_not_override_disabled_command() -> None:
    command = Command(
        command_id="project.open-recent",
        title="Open Recent Project",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            enabled=False,
        ),
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id="project.open-recent-menu",
            title="Open Recent Project",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (
                DynamicMenuItem(
                    title="BillingSystem",
                    command_id="project.open-recent",
                    enabled=True,
                ),
            ),
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert isinstance(
        resolved[0],
        ResolvedDynamicMenuContribution,
    )
    assert (
        resolved[0].items[0].state.enabled
        is False
    )


def test_hidden_dynamic_items_are_filtered_by_default() -> None:
    command = Command(
        command_id="file.open-recent",
        title="Open Recent File",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            visible=False,
        ),
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (
                DynamicMenuItem(
                    title="PAYROLL.cob",
                    command_id="file.open-recent",
                ),
            ),
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert isinstance(
        resolved[0],
        ResolvedDynamicMenuContribution,
    )
    assert resolved[0].items == ()


def test_hidden_dynamic_items_can_be_included() -> None:
    command = Command(
        command_id="file.open-recent",
        title="Open Recent File",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            visible=False,
        ),
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (
                DynamicMenuItem(
                    title="PAYROLL.cob",
                    command_id="file.open-recent",
                ),
            ),
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
        include_hidden=True,
    )

    assert isinstance(
        resolved[0],
        ResolvedDynamicMenuContribution,
    )
    assert len(
        resolved[0].items,
    ) == 1
    assert (
        resolved[0].items[0].state.visible
        is False
    )


def test_dynamic_menu_provider_producing_invalid_items_is_isolated() -> None:
    """A misbehaving provider (wrong return type) must not blank out the
    rest of the menu -- resolve_surface() isolates it and skips just
    this contribution instead of propagating the TypeError."""

    registry, service = _create_service()

    def invalid_provider(
        context: CommandContext,
    ) -> tuple[str, ...]:
        return (
            "not-an-item",
        )

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=invalid_provider,  # type: ignore[arg-type]
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert resolved == ()


def test_execute_dynamic_item_uses_provider_supplied_context() -> None:
    executed_paths: list[Any] = []

    def handler(
        context: CommandContext,
    ) -> Any:
        path = context.require(
            "path",
        )
        executed_paths.append(
            path,
        )
        return path

    command = Command(
        command_id="file.open-recent",
        title="Open Recent File",
        handler=handler,
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (
                DynamicMenuItem(
                    title="PAYROLL.cob",
                    command_id="file.open-recent",
                    context=CommandContext(
                        values={
                            "path": r"C:\source\PAYROLL.cob",
                        },
                    ),
                ),
            ),
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert isinstance(
        resolved[0],
        ResolvedDynamicMenuContribution,
    )

    result = service.execute_dynamic_item(
        resolved[0].items[0],
    )

    assert result == r"C:\source\PAYROLL.cob"
    assert executed_paths == [
        r"C:\source\PAYROLL.cob",
    ]


def test_execute_dynamic_item_rejects_provider_disabled_item() -> None:
    command = Command(
        command_id="file.open-recent",
        title="Open Recent File",
        handler=lambda context: None,
    )
    registry, service = _create_service(
        commands=(
            command,
        ),
    )

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            provider=lambda context: (
                DynamicMenuItem(
                    title="PAYROLL.cob",
                    command_id="file.open-recent",
                    enabled=False,
                ),
            ),
        )
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert isinstance(
        resolved[0],
        ResolvedDynamicMenuContribution,
    )

    with pytest.raises(
        CommandDisabledError,
        match="is disabled",
    ):
        service.execute_dynamic_item(
            resolved[0].items[0],
        )


def test_submenu_contribution_cannot_be_executed() -> None:
    registry, service = _create_service()

    registry.register(
        SubmenuContribution(
            contribution_id="file.new-menu",
            title="New",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            submenu_id="file.new",
            group_id="new",
        )
    )

    with pytest.raises(
        TypeError,
        match="Only direct command contributions",
    ):
        service.execute_contribution(
            "file.new-menu",
        )


def test_dynamic_menu_contribution_cannot_be_executed() -> None:
    registry, service = _create_service()

    registry.register(
        DynamicMenuContribution(
            contribution_id="file.open-recent-menu",
            title="Open Recent File",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
            group_id="open",
            provider=lambda context: (),
        )
    )

    with pytest.raises(
        TypeError,
        match="Only direct command contributions",
    ):
        service.execute_contribution(
            "file.open-recent-menu",
        )