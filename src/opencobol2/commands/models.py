"""Domain models for application commands."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


type CommandHandler = Callable[
    ["CommandContext"],
    Any,
]

type CommandStateProvider = Callable[
    ["CommandContext"],
    "CommandState",
]


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class CommandContext:
    """Execution context supplied to an application command."""

    values: Mapping[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        """Normalize command context values."""

        if not isinstance(
            self.values,
            Mapping,
        ):
            raise TypeError(
                "Command context values must be a mapping."
            )

        normalized_values = dict(
            self.values,
        )

        if not all(
            isinstance(
                key,
                str,
            )
            for key in normalized_values
        ):
            raise TypeError(
                "Command context keys must be strings."
            )

        object.__setattr__(
            self,
            "values",
            MappingProxyType(
                normalized_values,
            ),
        )

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Return a command context value."""

        return self.values.get(
            key,
            default,
        )

    def require(
        self,
        key: str,
    ) -> Any:
        """Return a required command context value."""

        try:
            return self.values[
                key
            ]
        except KeyError as error:
            raise KeyError(
                f"Required command context value is missing: "
                f"{key!r}."
            ) from error


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class CommandState:
    """Current user-interface state of an application command."""

    enabled: bool = True
    visible: bool = True
    checked: bool = False

    def __post_init__(self) -> None:
        """Validate command state flags."""

        for name, value in (
            (
                "enabled",
                self.enabled,
            ),
            (
                "visible",
                self.visible,
            ),
            (
                "checked",
                self.checked,
            ),
        ):
            if not isinstance(
                value,
                bool,
            ):
                raise TypeError(
                    f"Command state {name} must be a boolean."
                )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class Command:
    """Registered application command."""

    command_id: str
    title: str
    handler: CommandHandler
    description: str = ""
    category: str | None = None
    default_shortcuts: tuple[str, ...] = ()
    state_provider: CommandStateProvider | None = None

    def __post_init__(self) -> None:
        """Normalize and validate command metadata."""

        command_id = _require_non_empty_string(
            self.command_id,
            "Command ID",
        )
        title = _require_non_empty_string(
            self.title,
            "Command title",
        )

        if not callable(
            self.handler,
        ):
            raise TypeError(
                "Command handler must be callable."
            )

        if not isinstance(
            self.description,
            str,
        ):
            raise TypeError(
                "Command description must be a string."
            )

        description = self.description.strip()

        category = _normalize_optional_string(
            self.category,
            "Command category",
        )

        shortcuts = tuple(
            self.default_shortcuts,
        )

        if not all(
            isinstance(
                shortcut,
                str,
            )
            for shortcut in shortcuts
        ):
            raise TypeError(
                "Command default shortcuts must contain strings."
            )

        normalized_shortcuts = tuple(
            shortcut.strip()
            for shortcut in shortcuts
        )

        if any(
            not shortcut
            for shortcut in normalized_shortcuts
        ):
            raise ValueError(
                "Command default shortcuts must not be empty."
            )

        if (
            len(
                set(
                    normalized_shortcuts,
                )
            )
            != len(
                normalized_shortcuts,
            )
        ):
            raise ValueError(
                "Command default shortcuts must be unique."
            )

        if (
            self.state_provider is not None
            and not callable(
                self.state_provider,
            )
        ):
            raise TypeError(
                "Command state provider must be callable."
            )

        object.__setattr__(
            self,
            "command_id",
            command_id,
        )
        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "description",
            description,
        )
        object.__setattr__(
            self,
            "category",
            category,
        )
        object.__setattr__(
            self,
            "default_shortcuts",
            normalized_shortcuts,
        )

    def state(
        self,
        context: CommandContext,
    ) -> CommandState:
        """Return the current command state."""

        if not isinstance(
            context,
            CommandContext,
        ):
            raise TypeError(
                "Command context must be CommandContext."
            )

        if self.state_provider is None:
            return CommandState()

        state = self.state_provider(
            context,
        )

        if not isinstance(
            state,
            CommandState,
        ):
            raise TypeError(
                "Command state provider must return CommandState."
            )

        return state


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