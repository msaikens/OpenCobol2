"""Domain models for command surface contributions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from opencobol2.commands.models import (
    Command,
    CommandContext,
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

        _validate_surface_kind(
            self.surface_kind,
            "Command contribution surface kind",
        )
        _validate_ordering(
            self.group_order,
            "Command contribution group order",
        )
        _validate_ordering(
            self.order,
            "Command contribution order",
        )
        _validate_boolean(
            self.separator_before,
            "Command contribution separator before",
        )
        _validate_boolean(
            self.separator_after,
            "Command contribution separator after",
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
class SubmenuContribution:
    """Places one static submenu on an application surface."""

    contribution_id: str
    title: str
    surface_kind: CommandSurfaceKind
    surface_id: str
    submenu_id: str
    group_id: str = "default"
    group_order: int = 0
    order: int = 0
    separator_before: bool = False
    separator_after: bool = False

    def __post_init__(self) -> None:
        """Normalize and validate submenu contribution metadata."""

        contribution_id = _require_non_empty_string(
            self.contribution_id,
            "Submenu contribution ID",
        )
        title = _require_non_empty_string(
            self.title,
            "Submenu contribution title",
        )
        surface_id = _require_non_empty_string(
            self.surface_id,
            "Submenu contribution surface ID",
        )
        submenu_id = _require_non_empty_string(
            self.submenu_id,
            "Submenu contribution submenu ID",
        )
        group_id = _require_non_empty_string(
            self.group_id,
            "Submenu contribution group ID",
        )

        _validate_surface_kind(
            self.surface_kind,
            "Submenu contribution surface kind",
        )
        _validate_ordering(
            self.group_order,
            "Submenu contribution group order",
        )
        _validate_ordering(
            self.order,
            "Submenu contribution order",
        )
        _validate_boolean(
            self.separator_before,
            "Submenu contribution separator before",
        )
        _validate_boolean(
            self.separator_after,
            "Submenu contribution separator after",
        )

        object.__setattr__(
            self,
            "contribution_id",
            contribution_id,
        )
        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "surface_id",
            surface_id,
        )
        object.__setattr__(
            self,
            "submenu_id",
            submenu_id,
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
class DynamicMenuItem:
    """One ephemeral command entry produced for a dynamic menu."""

    title: str
    command_id: str
    context: CommandContext = field(
        default_factory=CommandContext,
    )
    enabled: bool | None = None
    secondary_text: str | None = None

    def __post_init__(self) -> None:
        """Normalize and validate dynamic menu item metadata."""

        title = _require_non_empty_string(
            self.title,
            "Dynamic menu item title",
        )
        command_id = _require_non_empty_string(
            self.command_id,
            "Dynamic menu item command ID",
        )

        if not isinstance(
            self.context,
            CommandContext,
        ):
            raise TypeError(
                "Dynamic menu item context must be CommandContext."
            )

        if (
            self.enabled is not None
            and not isinstance(
                self.enabled,
                bool,
            )
        ):
            raise TypeError(
                "Dynamic menu item enabled state must be a boolean "
                "or None."
            )

        secondary_text = _normalize_optional_string(
            self.secondary_text,
            "Dynamic menu item secondary text",
        )

        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "command_id",
            command_id,
        )
        object.__setattr__(
            self,
            "secondary_text",
            secondary_text,
        )


type DynamicMenuProvider = Callable[
    [CommandContext],
    Iterable[DynamicMenuItem],
]


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class DynamicMenuContribution:
    """Places one provider-backed dynamic menu on an application surface."""

    contribution_id: str
    title: str
    surface_kind: CommandSurfaceKind
    surface_id: str
    provider: DynamicMenuProvider
    group_id: str = "default"
    group_order: int = 0
    order: int = 0
    separator_before: bool = False
    separator_after: bool = False

    def __post_init__(self) -> None:
        """Normalize and validate dynamic menu contribution metadata."""

        contribution_id = _require_non_empty_string(
            self.contribution_id,
            "Dynamic menu contribution ID",
        )
        title = _require_non_empty_string(
            self.title,
            "Dynamic menu contribution title",
        )
        surface_id = _require_non_empty_string(
            self.surface_id,
            "Dynamic menu contribution surface ID",
        )
        group_id = _require_non_empty_string(
            self.group_id,
            "Dynamic menu contribution group ID",
        )

        _validate_surface_kind(
            self.surface_kind,
            "Dynamic menu contribution surface kind",
        )

        if not callable(
            self.provider,
        ):
            raise TypeError(
                "Dynamic menu contribution provider must be callable."
            )

        _validate_ordering(
            self.group_order,
            "Dynamic menu contribution group order",
        )
        _validate_ordering(
            self.order,
            "Dynamic menu contribution order",
        )
        _validate_boolean(
            self.separator_before,
            "Dynamic menu contribution separator before",
        )
        _validate_boolean(
            self.separator_after,
            "Dynamic menu contribution separator after",
        )

        object.__setattr__(
            self,
            "contribution_id",
            contribution_id,
        )
        object.__setattr__(
            self,
            "title",
            title,
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


type CommandSurfaceContribution = (
    CommandContribution
    | SubmenuContribution
    | DynamicMenuContribution
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


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ResolvedSubmenuContribution:
    """Static submenu contribution resolved for surface rendering."""

    contribution: SubmenuContribution

    def __post_init__(self) -> None:
        """Validate a resolved submenu contribution."""

        if not isinstance(
            self.contribution,
            SubmenuContribution,
        ):
            raise TypeError(
                "Resolved submenu contribution must be "
                "SubmenuContribution."
            )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ResolvedDynamicMenuItem:
    """Dynamic menu item resolved against current command state."""

    item: DynamicMenuItem
    command: Command
    state: CommandState

    def __post_init__(self) -> None:
        """Validate a resolved dynamic menu item."""

        if not isinstance(
            self.item,
            DynamicMenuItem,
        ):
            raise TypeError(
                "Resolved dynamic menu item must contain "
                "DynamicMenuItem."
            )

        if not isinstance(
            self.command,
            Command,
        ):
            raise TypeError(
                "Resolved dynamic menu item command must be Command."
            )

        if not isinstance(
            self.state,
            CommandState,
        ):
            raise TypeError(
                "Resolved dynamic menu item state must be CommandState."
            )

        if (
            self.item.command_id
            != self.command.command_id
        ):
            raise ValueError(
                "Resolved dynamic menu item command ID does not match "
                "the resolved command."
            )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ResolvedDynamicMenuContribution:
    """Dynamic menu contribution resolved with current menu items."""

    contribution: DynamicMenuContribution
    items: tuple[ResolvedDynamicMenuItem, ...]

    def __post_init__(self) -> None:
        """Validate a resolved dynamic menu contribution."""

        if not isinstance(
            self.contribution,
            DynamicMenuContribution,
        ):
            raise TypeError(
                "Resolved dynamic menu contribution must be "
                "DynamicMenuContribution."
            )

        items = tuple(
            self.items,
        )

        if not all(
            isinstance(
                item,
                ResolvedDynamicMenuItem,
            )
            for item in items
        ):
            raise TypeError(
                "Resolved dynamic menu contribution items must contain "
                "ResolvedDynamicMenuItem instances."
            )

        object.__setattr__(
            self,
            "items",
            items,
        )


type ResolvedCommandSurfaceContribution = (
    ResolvedCommandContribution
    | ResolvedSubmenuContribution
    | ResolvedDynamicMenuContribution
)


def _validate_surface_kind(
    value: CommandSurfaceKind,
    name: str,
) -> None:
    """Validate a command surface kind."""

    if not isinstance(
        value,
        CommandSurfaceKind,
    ):
        raise TypeError(
            f"{name} must be CommandSurfaceKind."
        )


def _validate_ordering(
    value: int,
    name: str,
) -> None:
    """Validate an integer ordering value."""

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
            f"{name} must be an integer."
        )


def _validate_boolean(
    value: bool,
    name: str,
) -> None:
    """Validate a boolean metadata flag."""

    if not isinstance(
        value,
        bool,
    ):
        raise TypeError(
            f"{name} must be a boolean."
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


def _normalize_optional_string(
    value: str | None,
    name: str,
) -> str | None:
    """Normalize an optional non-empty string."""

    if value is None:
        return None

    return _require_non_empty_string(
        value,
        name,
    )