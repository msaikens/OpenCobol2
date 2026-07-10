"""Application command contribution orchestration."""

from __future__ import annotations

from typing import Any

from opencobol2.commands import (
    CommandContext,
    CommandContributionRegistry,
    CommandSurfaceKind,
    ResolvedCommandContribution,
)
from opencobol2.services.commands import (
    CommandService,
)


class CommandContributionService:
    """Resolves command contributions against live command state."""

    def __init__(
        self,
        *,
        command_service: CommandService,
        contribution_registry: CommandContributionRegistry,
    ) -> None:
        """Initialize command contribution orchestration."""

        if not isinstance(
            command_service,
            CommandService,
        ):
            raise TypeError(
                "Command contribution service command service must "
                "be CommandService."
            )

        if not isinstance(
            contribution_registry,
            CommandContributionRegistry,
        ):
            raise TypeError(
                "Command contribution service registry must be "
                "CommandContributionRegistry."
            )

        self._command_service = command_service
        self._contribution_registry = (
            contribution_registry
        )

    @property
    def command_service(
        self,
    ) -> CommandService:
        """Return the application command service."""

        return self._command_service

    @property
    def contribution_registry(
        self,
    ) -> CommandContributionRegistry:
        """Return the command contribution registry."""

        return self._contribution_registry

    def resolve_surface(
        self,
        surface_kind: CommandSurfaceKind,
        surface_id: str,
        context: CommandContext | None = None,
        *,
        include_hidden: bool = False,
    ) -> tuple[ResolvedCommandContribution, ...]:
        """Resolve contributions for one application surface."""

        if not isinstance(
            include_hidden,
            bool,
        ):
            raise TypeError(
                "Include-hidden flag must be a boolean."
            )

        normalized_context = _normalize_context(
            context,
        )

        resolved_contributions: list[
            ResolvedCommandContribution
        ] = []

        for contribution in (
            self._contribution_registry.for_surface(
                surface_kind,
                surface_id,
            )
        ):
            command = self._command_service.get_command(
                contribution.command_id,
            )

            state = command.state(
                normalized_context,
            )

            if (
                not include_hidden
                and not state.visible
            ):
                continue

            resolved_contributions.append(
                ResolvedCommandContribution(
                    contribution=contribution,
                    command=command,
                    state=state,
                )
            )

        return tuple(
            resolved_contributions,
        )

    def execute_contribution(
        self,
        contribution_id: str,
        context: CommandContext | None = None,
    ) -> Any:
        """Execute the command referenced by a contribution."""

        contribution = (
            self._contribution_registry.get(
                contribution_id,
            )
        )

        return self._command_service.execute(
            contribution.command_id,
            context,
        )


def _normalize_context(
    context: CommandContext | None,
) -> CommandContext:
    """Return a concrete command context."""

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