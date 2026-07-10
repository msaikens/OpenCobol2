"""Application command registration."""

from __future__ import annotations

from opencobol2.commands.models import (
    Command,
)


class CommandAlreadyRegisteredError(
    ValueError,
):
    """Raised when a command ID is already registered."""


class CommandNotFoundError(
    LookupError,
):
    """Raised when a command ID is not registered."""


class CommandRegistry:
    """Ordered registry of application commands."""

    def __init__(
        self,
    ) -> None:
        """Initialize an empty command registry."""

        self._commands: dict[str, Command] = {}

    @property
    def commands(
        self,
    ) -> tuple[Command, ...]:
        """Return registered commands in registration order."""

        return tuple(
            self._commands.values(),
        )

    def register(
        self,
        command: Command,
    ) -> None:
        """Register one application command."""

        if not isinstance(
            command,
            Command,
        ):
            raise TypeError(
                "Command registry entries must be Command instances."
            )

        if command.command_id in self._commands:
            raise CommandAlreadyRegisteredError(
                "Command is already registered: "
                f"{command.command_id!r}."
            )

        self._commands[
            command.command_id
        ] = command

    def unregister(
        self,
        command_id: str,
    ) -> Command:
        """Remove and return a registered command."""

        normalized_command_id = _normalize_command_id(
            command_id,
        )

        try:
            return self._commands.pop(
                normalized_command_id,
            )
        except KeyError as error:
            raise CommandNotFoundError(
                "Command is not registered: "
                f"{normalized_command_id!r}."
            ) from error

    def get(
        self,
        command_id: str,
    ) -> Command:
        """Return a registered command."""

        normalized_command_id = _normalize_command_id(
            command_id,
        )

        try:
            return self._commands[
                normalized_command_id
            ]
        except KeyError as error:
            raise CommandNotFoundError(
                "Command is not registered: "
                f"{normalized_command_id!r}."
            ) from error

    def contains(
        self,
        command_id: str,
    ) -> bool:
        """Return whether a command ID is registered."""

        normalized_command_id = _normalize_command_id(
            command_id,
        )

        return (
            normalized_command_id
            in self._commands
        )


def _normalize_command_id(
    command_id: str,
) -> str:
    """Normalize and validate a command identifier."""

    if not isinstance(
        command_id,
        str,
    ):
        raise TypeError(
            "Command ID must be a string."
        )

    normalized_command_id = command_id.strip()

    if not normalized_command_id:
        raise ValueError(
            "Command ID must not be empty."
        )

    return normalized_command_id