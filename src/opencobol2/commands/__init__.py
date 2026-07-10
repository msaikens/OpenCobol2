"""Application command contracts and registries."""

from opencobol2.commands.contribution_registry import (
    CommandContributionAlreadyRegisteredError,
    CommandContributionNotFoundError,
    CommandContributionRegistry,
)
from opencobol2.commands.contributions import (
    CommandContribution,
    CommandSurfaceContribution,
    CommandSurfaceKind,
    DynamicMenuContribution,
    DynamicMenuItem,
    DynamicMenuProvider,
    ResolvedCommandContribution,
    ResolvedCommandSurfaceContribution,
    ResolvedDynamicMenuContribution,
    ResolvedDynamicMenuItem,
    ResolvedSubmenuContribution,
    SubmenuContribution,
)
from opencobol2.commands.models import (
    Command,
    CommandContext,
    CommandHandler,
    CommandState,
    CommandStateProvider,
)
from opencobol2.commands.registry import (
    CommandAlreadyRegisteredError,
    CommandNotFoundError,
    CommandRegistry,
)


__all__ = [
    "Command",
    "CommandAlreadyRegisteredError",
    "CommandContext",
    "CommandContribution",
    "CommandContributionAlreadyRegisteredError",
    "CommandContributionNotFoundError",
    "CommandContributionRegistry",
    "CommandHandler",
    "CommandNotFoundError",
    "CommandRegistry",
    "CommandState",
    "CommandStateProvider",
    "CommandSurfaceContribution",
    "CommandSurfaceKind",
    "DynamicMenuContribution",
    "DynamicMenuItem",
    "DynamicMenuProvider",
    "ResolvedCommandContribution",
    "ResolvedCommandSurfaceContribution",
    "ResolvedDynamicMenuContribution",
    "ResolvedDynamicMenuItem",
    "ResolvedSubmenuContribution",
    "SubmenuContribution",
]