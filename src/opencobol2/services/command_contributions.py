"""Application command contribution orchestration."""

from __future__ import annotations

from typing import Any

from opencobol2.commands import (
    CommandContext,
    CommandContribution,
    CommandContributionRegistry,
    CommandState,
    CommandSurfaceKind,
    DynamicMenuContribution,
    DynamicMenuItem,
    ResolvedCommandContribution,
    ResolvedCommandSurfaceContribution,
    ResolvedDynamicMenuContribution,
    ResolvedDynamicMenuItem,
    ResolvedSubmenuContribution,
    SubmenuContribution,
)
from opencobol2.services.commands import (
    CommandDisabledError,
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
    ) -> tuple[ResolvedCommandSurfaceContribution, ...]:
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
            ResolvedCommandSurfaceContribution
        ] = []

        for contribution in (
            self._contribution_registry.for_surface(
                surface_kind,
                surface_id,
            )
        ):
            if isinstance(
                contribution,
                CommandContribution,
            ):
                resolved = self._resolve_command_contribution(
                    contribution,
                    normalized_context,
                )

                if (
                    not include_hidden
                    and not resolved.state.visible
                ):
                    continue

                resolved_contributions.append(
                    resolved,
                )
                continue

            if isinstance(
                contribution,
                SubmenuContribution,
            ):
                resolved_contributions.append(
                    ResolvedSubmenuContribution(
                        contribution=contribution,
                    )
                )
                continue

            if isinstance(
                contribution,
                DynamicMenuContribution,
            ):
                resolved_contributions.append(
                    self._resolve_dynamic_menu_contribution(
                        contribution,
                        normalized_context,
                        include_hidden=include_hidden,
                    )
                )
                continue

            raise TypeError(
                "Unsupported command surface contribution type: "
                f"{type(contribution).__name__}."
            )

        return tuple(
            resolved_contributions,
        )

    def execute_contribution(
        self,
        contribution_id: str,
        context: CommandContext | None = None,
    ) -> Any:
        """Execute the command referenced by a direct contribution."""

        contribution = (
            self._contribution_registry.get(
                contribution_id,
            )
        )

        if not isinstance(
            contribution,
            CommandContribution,
        ):
            raise TypeError(
                "Only direct command contributions can be executed."
            )

        return self._command_service.execute(
            contribution.command_id,
            context,
        )

    def execute_dynamic_item(
        self,
        item: ResolvedDynamicMenuItem,
    ) -> Any:
        """Execute one previously resolved dynamic menu item."""

        if not isinstance(
            item,
            ResolvedDynamicMenuItem,
        ):
            raise TypeError(
                "Dynamic menu execution item must be "
                "ResolvedDynamicMenuItem."
            )

        if not item.state.enabled:
            raise CommandDisabledError(
                "Dynamic menu item command is disabled: "
                f"{item.command.command_id!r}."
            )

        return self._command_service.execute(
            item.command.command_id,
            item.item.context,
        )

    def _resolve_command_contribution(
        self,
        contribution: CommandContribution,
        context: CommandContext,
    ) -> ResolvedCommandContribution:
        """Resolve one direct command contribution."""

        command = self._command_service.get_command(
            contribution.command_id,
        )
        state = command.state(
            context,
        )

        return ResolvedCommandContribution(
            contribution=contribution,
            command=command,
            state=state,
        )

    def _resolve_dynamic_menu_contribution(
        self,
        contribution: DynamicMenuContribution,
        context: CommandContext,
        *,
        include_hidden: bool,
    ) -> ResolvedDynamicMenuContribution:
        """Resolve one provider-backed dynamic menu contribution."""

        produced_items = contribution.provider(
            context,
        )

        try:
            items = tuple(
                produced_items,
            )
        except TypeError as error:
            raise TypeError(
                "Dynamic menu provider must return an iterable of "
                "DynamicMenuItem instances."
            ) from error

        resolved_items: list[
            ResolvedDynamicMenuItem
        ] = []

        for item in items:
            if not isinstance(
                item,
                DynamicMenuItem,
            ):
                raise TypeError(
                    "Dynamic menu provider must return an iterable of "
                    "DynamicMenuItem instances."
                )

            command = self._command_service.get_command(
                item.command_id,
            )
            command_state = command.state(
                item.context,
            )
            state = _apply_dynamic_item_enabled_state(
                command_state,
                item.enabled,
            )

            if (
                not include_hidden
                and not state.visible
            ):
                continue

            resolved_items.append(
                ResolvedDynamicMenuItem(
                    item=item,
                    command=command,
                    state=state,
                )
            )

        return ResolvedDynamicMenuContribution(
            contribution=contribution,
            items=tuple(
                resolved_items,
            ),
        )


def _apply_dynamic_item_enabled_state(
    command_state: CommandState,
    item_enabled: bool | None,
) -> CommandState:
    """Apply an item's additional enabled-state restriction."""

    if item_enabled is None:
        return command_state

    return CommandState(
        enabled=(
            command_state.enabled
            and item_enabled
        ),
        visible=command_state.visible,
        checked=command_state.checked,
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