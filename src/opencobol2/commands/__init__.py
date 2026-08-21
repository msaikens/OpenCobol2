"""Application command contracts and registries.

Re-exports the command and command-contribution domain models
(:class:`Command`, :class:`CommandContribution`, and related types),
the registries that track them (:class:`CommandRegistry`,
:class:`CommandContributionRegistry`), and the built-in command
handlers and factory functions that wire the application's own
commands and menu contributions into those registries.
"""

from opencobol2.commands.builtins import (
    AccessibilityCommandService,
    BuiltInCommandHandlerNotConfiguredError,
    BuiltInCommandHandlers,
    BuiltInCommandIds,
    BuiltInCommandSurfaceIds,
    BuiltInMenuContributionIds,
    ToolWindowCommandService,
    create_builtin_command_contribution_registry,
    create_builtin_command_registry,
)
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
    "AccessibilityCommandService",
    "BuiltInCommandHandlerNotConfiguredError",
    "BuiltInCommandHandlers",
    "BuiltInCommandIds",
    "BuiltInCommandSurfaceIds",
    "BuiltInMenuContributionIds",
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
    "ToolWindowCommandService",
    "create_builtin_command_contribution_registry",
    "create_builtin_command_registry",
]