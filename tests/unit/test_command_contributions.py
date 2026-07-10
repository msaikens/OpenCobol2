"""Unit tests for command contribution domain models."""

from __future__ import annotations

import pytest

from opencobol2.commands import (
    Command,
    CommandContribution,
    CommandState,
    CommandSurfaceKind,
    ResolvedCommandContribution,
)


def _create_command() -> Command:
    """Create a command for contribution tests."""

    return Command(
        command_id="file.save",
        title="Save",
        handler=lambda context: None,
    )


def test_contribution_normalizes_identifiers() -> None:
    contribution = CommandContribution(
        contribution_id="  core.menu.file.save  ",
        command_id="  file.save  ",
        surface_kind=CommandSurfaceKind.MENU,
        surface_id="  file  ",
        group_id="  save  ",
    )

    assert (
        contribution.contribution_id
        == "core.menu.file.save"
    )
    assert contribution.command_id == "file.save"
    assert contribution.surface_id == "file"
    assert contribution.group_id == "save"


def test_contribution_defaults_are_deterministic() -> None:
    contribution = CommandContribution(
        contribution_id="core.menu.file.save",
        command_id="file.save",
        surface_kind=CommandSurfaceKind.MENU,
        surface_id="file",
    )

    assert contribution.group_id == "default"
    assert contribution.group_order == 0
    assert contribution.order == 0
    assert contribution.separator_before is False
    assert contribution.separator_after is False


@pytest.mark.parametrize(
    "field_name",
    [
        "group_order",
        "order",
    ],
)
def test_contribution_order_values_must_be_integers(
    field_name: str,
) -> None:
    values = {
        "contribution_id": "core.menu.file.save",
        "command_id": "file.save",
        "surface_kind": CommandSurfaceKind.MENU,
        "surface_id": "file",
        field_name: True,
    }

    with pytest.raises(
        TypeError,
        match="must be an integer",
    ):
        CommandContribution(
            **values,
        )


def test_resolved_contribution_preserves_command_state() -> None:
    command = _create_command()
    contribution = CommandContribution(
        contribution_id="core.menu.file.save",
        command_id=command.command_id,
        surface_kind=CommandSurfaceKind.MENU,
        surface_id="file",
    )
    state = CommandState(
        enabled=False,
    )

    resolved = ResolvedCommandContribution(
        contribution=contribution,
        command=command,
        state=state,
    )

    assert resolved.contribution is contribution
    assert resolved.command is command
    assert resolved.state is state


def test_resolved_contribution_rejects_command_mismatch() -> None:
    command = Command(
        command_id="file.open",
        title="Open",
        handler=lambda context: None,
    )
    contribution = CommandContribution(
        contribution_id="core.menu.file.save",
        command_id="file.save",
        surface_kind=CommandSurfaceKind.MENU,
        surface_id="file",
    )

    with pytest.raises(
        ValueError,
        match="command ID does not match",
    ):
        ResolvedCommandContribution(
            contribution=contribution,
            command=command,
            state=CommandState(),
        )