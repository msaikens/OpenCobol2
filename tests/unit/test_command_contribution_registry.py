"""Unit tests for command contribution registration."""

from __future__ import annotations

import pytest

from opencobol2.commands import (
    CommandContribution,
    CommandContributionAlreadyRegisteredError,
    CommandContributionNotFoundError,
    CommandContributionRegistry,
    CommandSurfaceKind,
)


def _create_contribution(
    contribution_id: str,
    *,
    command_id: str = "file.save",
    surface_kind: CommandSurfaceKind = (
        CommandSurfaceKind.MENU
    ),
    surface_id: str = "file",
    group_order: int = 0,
    order: int = 0,
) -> CommandContribution:
    """Create a contribution for registry tests."""

    return CommandContribution(
        contribution_id=contribution_id,
        command_id=command_id,
        surface_kind=surface_kind,
        surface_id=surface_id,
        group_order=group_order,
        order=order,
    )


def test_registry_preserves_registration_order() -> None:
    registry = CommandContributionRegistry()

    first = _create_contribution(
        "core.menu.file.save",
    )
    second = _create_contribution(
        "core.menu.file.save-as",
        command_id="file.save-as",
    )

    registry.register(
        first,
    )
    registry.register(
        second,
    )

    assert registry.contributions == (
        first,
        second,
    )


def test_registry_rejects_duplicate_contribution_id() -> None:
    registry = CommandContributionRegistry()

    registry.register(
        _create_contribution(
            "core.menu.file.save",
        )
    )

    with pytest.raises(
        CommandContributionAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(
            _create_contribution(
                "core.menu.file.save",
                command_id="file.open",
            )
        )


def test_registry_unregister_returns_removed_contribution() -> None:
    registry = CommandContributionRegistry()
    contribution = _create_contribution(
        "core.menu.file.save",
    )

    registry.register(
        contribution,
    )

    removed = registry.unregister(
        "core.menu.file.save",
    )

    assert removed is contribution
    assert registry.contributions == ()


def test_registry_rejects_unknown_contribution() -> None:
    registry = CommandContributionRegistry()

    with pytest.raises(
        CommandContributionNotFoundError,
        match="is not registered",
    ):
        registry.get(
            "missing.contribution",
        )


def test_surface_query_filters_kind_and_surface_id() -> None:
    registry = CommandContributionRegistry()

    file_menu = _create_contribution(
        "core.menu.file.save",
    )
    edit_menu = _create_contribution(
        "core.menu.edit.copy",
        command_id="edit.copy",
        surface_id="edit",
    )
    toolbar = _create_contribution(
        "core.toolbar.main.save",
        surface_kind=CommandSurfaceKind.TOOLBAR,
        surface_id="main",
    )

    for contribution in (
        file_menu,
        edit_menu,
        toolbar,
    ):
        registry.register(
            contribution,
        )

    assert registry.for_surface(
        CommandSurfaceKind.MENU,
        "file",
    ) == (
        file_menu,
    )


def test_surface_query_orders_by_group_then_item_order() -> None:
    registry = CommandContributionRegistry()

    third = _create_contribution(
        "third",
        group_order=20,
        order=10,
    )
    first = _create_contribution(
        "first",
        group_order=10,
        order=10,
    )
    second = _create_contribution(
        "second",
        group_order=10,
        order=20,
    )

    for contribution in (
        third,
        second,
        first,
    ):
        registry.register(
            contribution,
        )

    assert registry.for_surface(
        CommandSurfaceKind.MENU,
        "file",
    ) == (
        first,
        second,
        third,
    )


def test_equal_order_values_preserve_registration_order() -> None:
    registry = CommandContributionRegistry()

    first = _create_contribution(
        "first",
    )
    second = _create_contribution(
        "second",
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