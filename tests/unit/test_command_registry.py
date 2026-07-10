"""Unit tests for application command registration."""

from __future__ import annotations

import pytest

from opencobol2.commands import (
    Command,
    CommandAlreadyRegisteredError,
    CommandContext,
    CommandNotFoundError,
    CommandRegistry,
)


def _create_command(
    command_id: str,
) -> Command:
    """Create a simple command for registry tests."""

    return Command(
        command_id=command_id,
        title=command_id,
        handler=lambda context: None,
    )


def test_registry_preserves_registration_order() -> None:
    registry = CommandRegistry()

    first = _create_command(
        "file.new",
    )
    second = _create_command(
        "file.open",
    )

    registry.register(
        first,
    )
    registry.register(
        second,
    )

    assert registry.commands == (
        first,
        second,
    )


def test_registry_get_returns_registered_command() -> None:
    registry = CommandRegistry()
    command = _create_command(
        "file.save",
    )

    registry.register(
        command,
    )

    assert (
        registry.get(
            "file.save",
        )
        is command
    )


def test_registry_rejects_duplicate_command_id() -> None:
    registry = CommandRegistry()

    registry.register(
        _create_command(
            "file.save",
        )
    )

    with pytest.raises(
        CommandAlreadyRegisteredError,
        match="Command is already registered",
    ):
        registry.register(
            _create_command(
                "file.save",
            )
        )


def test_registry_unregister_returns_removed_command() -> None:
    registry = CommandRegistry()
    command = _create_command(
        "file.close",
    )

    registry.register(
        command,
    )

    removed = registry.unregister(
        "file.close",
    )

    assert removed is command
    assert (
        registry.contains(
            "file.close",
        )
        is False
    )


def test_registry_rejects_unknown_command() -> None:
    registry = CommandRegistry()

    with pytest.raises(
        CommandNotFoundError,
        match="Command is not registered",
    ):
        registry.get(
            "missing.command",
        )


def test_registry_requires_command_instances() -> None:
    registry = CommandRegistry()

    with pytest.raises(
        TypeError,
        match="must be Command instances",
    ):
        registry.register(
            "file.save",  # type: ignore[arg-type]
        )