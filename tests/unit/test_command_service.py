"""Unit tests for application command orchestration."""

from __future__ import annotations

import pytest

from opencobol2.commands import (
    Command,
    CommandContext,
    CommandRegistry,
    CommandState,
)
from opencobol2.services.commands import (
    CommandDisabledError,
    CommandService,
)


def _create_service(
    *commands: Command,
) -> CommandService:
    """Create a command service with registered commands."""

    registry = CommandRegistry()

    for command in commands:
        registry.register(
            command,
        )

    return CommandService(
        registry=registry,
    )


def test_service_returns_registered_command() -> None:
    command = Command(
        command_id="file.new",
        title="New File",
        handler=lambda context: None,
    )

    service = _create_service(
        command,
    )

    assert (
        service.get_command(
            "file.new",
        )
        is command
    )


def test_service_returns_current_command_state() -> None:
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
        command,
    )

    disabled_state = service.get_state(
        "file.save",
    )

    enabled_state = service.get_state(
        "file.save",
        CommandContext(
            values={
                "active_document": "program.cob",
            },
        ),
    )

    assert disabled_state.enabled is False
    assert enabled_state.enabled is True


def test_service_executes_handler_with_context() -> None:
    captured_context = None

    def handler(
        context: CommandContext,
    ) -> str:
        nonlocal captured_context

        captured_context = context

        return context.require(
            "document_name",
        )

    command = Command(
        command_id="example.return-document",
        title="Return Document",
        handler=handler,
    )

    service = _create_service(
        command,
    )

    context = CommandContext(
        values={
            "document_name": "program.cob",
        },
    )

    result = service.execute(
        "example.return-document",
        context,
    )

    assert result == "program.cob"
    assert captured_context is context


def test_service_supplies_empty_context_when_omitted() -> None:
    captured_context = None

    def handler(
        context: CommandContext,
    ) -> None:
        nonlocal captured_context

        captured_context = context

    command = Command(
        command_id="example.empty-context",
        title="Empty Context",
        handler=handler,
    )

    service = _create_service(
        command,
    )

    service.execute(
        "example.empty-context",
    )

    assert isinstance(
        captured_context,
        CommandContext,
    )
    assert captured_context.values == {}


def test_service_rejects_disabled_command_execution() -> None:
    executed = False

    def handler(
        context: CommandContext,
    ) -> None:
        nonlocal executed

        executed = True

    command = Command(
        command_id="file.save",
        title="Save",
        handler=handler,
        state_provider=lambda context: CommandState(
            enabled=False,
        ),
    )

    service = _create_service(
        command,
    )

    with pytest.raises(
        CommandDisabledError,
        match="Command is disabled",
    ):
        service.execute(
            "file.save",
        )

    assert executed is False


def test_invisible_enabled_command_can_execute_programmatically() -> None:
    command = Command(
        command_id="example.hidden",
        title="Hidden Command",
        handler=lambda context: "executed",
        state_provider=lambda context: CommandState(
            enabled=True,
            visible=False,
        ),
    )

    service = _create_service(
        command,
    )

    assert (
        service.execute(
            "example.hidden",
        )
        == "executed"
    )


def test_command_state_is_evaluated_once_per_execution() -> None:
    state_evaluation_count = 0

    def state_provider(
        context: CommandContext,
    ) -> CommandState:
        nonlocal state_evaluation_count

        state_evaluation_count += 1

        return CommandState(
            enabled=True,
        )

    command = Command(
        command_id="example.once",
        title="Evaluate Once",
        handler=lambda context: None,
        state_provider=state_provider,
    )

    service = _create_service(
        command,
    )

    service.execute(
        "example.once",
    )

    assert state_evaluation_count == 1