"""Domain models for command surface contributions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from opencobol2.commands.models import (
    Command,
    CommandState,
)


class CommandSurfaceKind(StrEnum):
    """Supported application command contribution surfaces."""

    MENU = "menu"
    TOOLBAR = "toolbar"
    CONTEXT_MENU = "context-menu"


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class CommandContribution:
    """Places one registered command on an application surface."""

    contribution_id: str
    command_id: str
    surface_kind: CommandSurfaceKind
    surface_id: str
    group_id: str = "default"
    group_order: int = 0
    order: int = 0
    separator_before: bool = False
    separator_after: bool = False

    def __post_init__(self) -> None:
        """Normalize and validate command contribution metadata."""

        contribution_id = _require_non_empty_string(
            self.contribution_id,
            "Command contribution ID",
        )
        command_id = _require_non_empty_string(
            self.command_id,
            "Command contribution command ID",
        )
        surface_id = _require_non_empty_string(
            self.surface_id,
            "Command contribution surface ID",
        )
        group_id = _require_non_empty_string(
            self.group_id,
            "Command contribution group ID",
        )

        if not isinstance(
            self.surface_kind,
            CommandSurfaceKind,
        ):
            raise TypeError(
                "Command contribution surface kind must be "
                "CommandSurfaceKind."
            )

        for name, value in (
            (
                "group order",
                self.group_order,
            ),
            (
                "order",
                self.order,
            ),
        ):
            if (
                not isinstance(
                    value,
                    int,
                )
                or isinstance(
                    value,
                    bool,
                )
            ):
                raise TypeError(
                    f"Command contribution {name} must be an integer."
                )

        for name, value in (
            (
                "separator before",
                self.separator_before,
            ),
            (
                "separator after",
                self.separator_after,
            ),
        ):
            if not isinstance(
                value,
                bool,
            ):
                raise TypeError(
                    f"Command contribution {name} must be a boolean."
                )

        object.__setattr__(
            self,
            "contribution_id",
            contribution_id,
        )
        object.__setattr__(
            self,
            "command_id",
            command_id,
        )
        object.__setattr__(
            self,
            "surface_id",
            surface_id,
        )
        object.__setattr__(
            self,
            "group_id",
            group_id,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ResolvedCommandContribution:
    """Command contribution resolved against current command state."""

    contribution: CommandContribution
    command: Command
    state: CommandState

    def __post_init__(self) -> None:
        """Validate a resolved command contribution."""

        if not isinstance(
            self.contribution,
            CommandContribution,
        ):
            raise TypeError(
                "Resolved contribution must be CommandContribution."
            )

        if not isinstance(
            self.command,
            Command,
        ):
            raise TypeError(
                "Resolved contribution command must be Command."
            )

        if not isinstance(
            self.state,
            CommandState,
        ):
            raise TypeError(
                "Resolved contribution state must be CommandState."
            )

        if (
            self.contribution.command_id
            != self.command.command_id
        ):
            raise ValueError(
                "Resolved contribution command ID does not match "
                "the resolved command."
            )


def _require_non_empty_string(
    value: str,
    name: str,
) -> str:
    """Require and normalize a non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized_value