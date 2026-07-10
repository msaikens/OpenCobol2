"""Application command orchestration services."""

from __future__ import annotations

from typing import Any

from opencobol2.commands import (
    Command,
    CommandContext,
    CommandRegistry,
    CommandState,
)


class CommandDisabledError(
    RuntimeError,
):
    """Raised when execution is requested for a disabled command."""


class CommandService:
    """Queries and executes registered application commands."""

    def __init__(
        self,
        *,
        registry: CommandRegistry,
    ) -> None:
        """Initialize command orchestration."""

        if not isinstance(
            registry,
            CommandRegistry,
        ):
            raise TypeError(
                "Command service registry must be CommandRegistry."
            )

        self._registry = registry

    @property
    def registry(
        self,
    ) -> CommandRegistry:
        """Return the application command registry."""

        return self._registry

    def get_command(
        self,
        command_id: str,
    ) -> Command:
        """Return a registered application command."""

        return self._registry.get(
            command_id,
        )

    def get_state(
        self,
        command_id: str,
        context: CommandContext | None = None,
    ) -> CommandState:
        """Return the current state of a command."""

        command = self.get_command(
            command_id,
        )

        return command.state(
            _normalize_context(
                context,
            )
        )

    def execute(
        self,
        command_id: str,
        context: CommandContext | None = None,
    ) -> Any:
        """Execute an enabled application command."""

        command = self.get_command(
            command_id,
        )
        normalized_context = _normalize_context(
            context,
        )

        state = command.state(
            normalized_context,
        )

        if not state.enabled:
            raise CommandDisabledError(
                "Command is disabled: "
                f"{command.command_id!r}."
            )

        return command.handler(
            normalized_context,
        )


def _normalize_context(
    context: CommandContext | None,
) -> CommandContext:
    """Return a concrete command execution context."""

    if context is None:
        return CommandContext()

    if not isinstance(
        context,
        CommandContext,
    ):
        raise TypeError(
            "Command context must be CommandContext."
        )

    return context