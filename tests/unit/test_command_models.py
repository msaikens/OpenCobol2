"""Unit tests for application command domain models."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from opencobol2.commands import (
    Command,
    CommandContext,
    CommandState,
)


def _no_op_handler(
    context: CommandContext,
) -> None:
    """Provide a reusable no-op command handler."""


def test_command_context_copies_values() -> None:
    values = {
        "active_document": "program.cob",
    }

    context = CommandContext(
        values=values,
    )

    values[
        "active_document"
    ] = "other.cob"

    assert (
        context.values["active_document"]
        == "program.cob"
    )
    assert isinstance(
        context.values,
        MappingProxyType,
    )


def test_command_context_require_returns_value() -> None:
    context = CommandContext(
        values={
            "workspace": "example",
        },
    )

    assert (
        context.require(
            "workspace",
        )
        == "example"
    )


def test_command_context_require_rejects_missing_value() -> None:
    context = CommandContext()

    with pytest.raises(
        KeyError,
        match="Required command context value is missing",
    ):
        context.require(
            "active_document",
        )


def test_command_normalizes_metadata() -> None:
    command = Command(
        command_id="  file.save  ",
        title="  Save  ",
        description="  Save the active document.  ",
        category="  File  ",
        default_shortcuts=(
            "  Ctrl+S  ",
        ),
        handler=_no_op_handler,
    )

    assert command.command_id == "file.save"
    assert command.title == "Save"
    assert (
        command.description
        == "Save the active document."
    )
    assert command.category == "File"
    assert command.default_shortcuts == (
        "Ctrl+S",
    )


def test_command_requires_unique_default_shortcuts() -> None:
    with pytest.raises(
        ValueError,
        match="default shortcuts must be unique",
    ):
        Command(
            command_id="file.save",
            title="Save",
            handler=_no_op_handler,
            default_shortcuts=(
                "Ctrl+S",
                "Ctrl+S",
            ),
        )


def test_command_without_state_provider_is_enabled_and_visible() -> None:
    command = Command(
        command_id="file.new",
        title="New File",
        handler=_no_op_handler,
    )

    assert command.state(
        CommandContext(),
    ) == CommandState(
        enabled=True,
        visible=True,
        checked=False,
    )


def test_command_uses_state_provider() -> None:
    command = Command(
        command_id="file.save",
        title="Save",
        handler=_no_op_handler,
        state_provider=lambda context: CommandState(
            enabled=(
                context.get(
                    "active_document",
                )
                is not None
            ),
        ),
    )

    assert (
        command.state(
            CommandContext(),
        ).enabled
        is False
    )
    assert (
        command.state(
            CommandContext(
                values={
                    "active_document": "program.cob",
                },
            ),
        ).enabled
        is True
    )


def test_state_provider_must_return_command_state() -> None:
    command = Command(
        command_id="example.invalid-state",
        title="Invalid State",
        handler=_no_op_handler,
        state_provider=lambda context: True,
    )

    with pytest.raises(
        TypeError,
        match="must return CommandState",
    ):
        command.state(
            CommandContext(),
        )