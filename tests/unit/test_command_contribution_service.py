"""Unit tests for command contribution orchestration."""

from __future__ import annotations

import pytest

from opencobol2.commands import (
    Command,
    CommandContext,
    CommandContribution,
    CommandContributionRegistry,
    CommandRegistry,
    CommandState,
    CommandSurfaceKind,
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
    commands: tuple[Command, ...],
    contributions: tuple[
        CommandContribution,
        ...,
    ],
) -> CommandContributionService:
    """Create command contribution orchestration."""

    command_registry = CommandRegistry()

    for command in commands:
        command_registry.register(
            command,
        )

    contribution_registry = (
        CommandContributionRegistry()
    )

    for contribution in contributions:
        contribution_registry.register(
            contribution,
        )

    return CommandContributionService(
        command_service=CommandService(
            registry=command_registry,
        ),
        contribution_registry=contribution_registry,
    )


def _create_contribution(
    *,
    contribution_id: str,
    command_id: str,
    order: int = 0,
) -> CommandContribution:
    """Create a File-menu contribution."""

    return CommandContribution(
        contribution_id=contribution_id,
        command_id=command_id,
        surface_kind=CommandSurfaceKind.MENU,
        surface_id="file",
        order=order,
    )


def test_service_resolves_command_and_current_state() -> None:
    command = Command(
        command_id="file.save",
        title="Save",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            enabled=(
                context.get(
                    "active_document",
                )
                is not None
            ),
        ),
    )

    service = _create_service(
        commands=(
            command,
        ),
        contributions=(
            _create_contribution(
                contribution_id="core.menu.file.save",
                command_id="file.save",
            ),
        ),
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
        CommandContext(
            values={
                "active_document": "program.cob",
            },
        ),
    )

    assert len(
        resolved,
    ) == 1
    assert resolved[0].command is command
    assert resolved[0].state.enabled is True


def test_service_filters_hidden_commands_by_default() -> None:
    command = Command(
        command_id="file.hidden",
        title="Hidden",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            visible=False,
        ),
    )

    service = _create_service(
        commands=(
            command,
        ),
        contributions=(
            _create_contribution(
                contribution_id="core.menu.file.hidden",
                command_id="file.hidden",
            ),
        ),
    )

    assert service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    ) == ()


def test_service_can_include_hidden_commands() -> None:
    command = Command(
        command_id="file.hidden",
        title="Hidden",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            visible=False,
        ),
    )

    service = _create_service(
        commands=(
            command,
        ),
        contributions=(
            _create_contribution(
                contribution_id="core.menu.file.hidden",
                command_id="file.hidden",
            ),
        ),
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
        include_hidden=True,
    )

    assert len(
        resolved,
    ) == 1
    assert resolved[0].state.visible is False


def test_service_preserves_contribution_order() -> None:
    save = Command(
        command_id="file.save",
        title="Save",
        handler=lambda context: None,
    )
    close = Command(
        command_id="file.close",
        title="Close",
        handler=lambda context: None,
    )

    service = _create_service(
        commands=(
            save,
            close,
        ),
        contributions=(
            _create_contribution(
                contribution_id="core.menu.file.close",
                command_id="file.close",
                order=20,
            ),
            _create_contribution(
                contribution_id="core.menu.file.save",
                command_id="file.save",
                order=10,
            ),
        ),
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert tuple(
        item.command.command_id
        for item in resolved
    ) == (
        "file.save",
        "file.close",
    )


def test_service_skips_contribution_for_missing_command() -> None:
    """A contribution referencing a stale/typo'd command ID must not
    blank out an entire menu -- it's isolated and skipped instead."""

    service = _create_service(
        commands=(),
        contributions=(
            _create_contribution(
                contribution_id="plugin.menu.file.missing",
                command_id="plugin.missing",
            ),
        ),
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert resolved == ()


def test_service_skips_only_broken_contribution_among_others() -> None:
    working_command = Command(
        command_id="file.save",
        title="Save",
        handler=lambda context: None,
    )
    service = _create_service(
        commands=(working_command,),
        contributions=(
            _create_contribution(
                contribution_id="plugin.menu.file.missing",
                command_id="plugin.missing",
            ),
            _create_contribution(
                contribution_id="file.menu.save",
                command_id="file.save",
                order=1,
            ),
        ),
    )

    resolved = service.resolve_surface(
        CommandSurfaceKind.MENU,
        "file",
    )

    assert len(resolved) == 1
    assert resolved[0].command.command_id == "file.save"


def test_validate_contributions_reports_missing_command() -> None:
    service = _create_service(
        commands=(),
        contributions=(
            _create_contribution(
                contribution_id="plugin.menu.file.missing",
                command_id="plugin.missing",
            ),
        ),
    )

    assert service.validate_contributions() == (
        "plugin.menu.file.missing",
    )


def test_validate_contributions_returns_empty_when_all_resolve() -> None:
    working_command = Command(
        command_id="file.save",
        title="Save",
        handler=lambda context: None,
    )
    service = _create_service(
        commands=(working_command,),
        contributions=(
            _create_contribution(
                contribution_id="file.menu.save",
                command_id="file.save",
            ),
        ),
    )

    assert service.validate_contributions() == ()


def test_execute_contribution_invokes_referenced_command() -> None:
    command = Command(
        command_id="file.save",
        title="Save",
        handler=lambda context: context.require(
            "document",
        ),
    )

    service = _create_service(
        commands=(
            command,
        ),
        contributions=(
            _create_contribution(
                contribution_id="core.menu.file.save",
                command_id="file.save",
            ),
        ),
    )

    result = service.execute_contribution(
        "core.menu.file.save",
        CommandContext(
            values={
                "document": "program.cob",
            },
        ),
    )

    assert result == "program.cob"


def test_execute_contribution_respects_command_enabled_state() -> None:
    command = Command(
        command_id="file.save",
        title="Save",
        handler=lambda context: None,
        state_provider=lambda context: CommandState(
            enabled=False,
        ),
    )

    service = _create_service(
        commands=(
            command,
        ),
        contributions=(
            _create_contribution(
                contribution_id="core.menu.file.save",
                command_id="file.save",
            ),
        ),
    )

    with pytest.raises(
        CommandDisabledError,
        match="Command is disabled",
    ):
        service.execute_contribution(
            "core.menu.file.save",
        )