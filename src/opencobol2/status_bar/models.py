"""Domain models for status bar item contributions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class StatusBarItemAlignment(StrEnum):
    """Supported status bar placement groups."""

    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True, kw_only=True)
class StatusBarItemContent:
    """The current displayable state of one status bar item."""

    text: str
    tooltip: str | None = None
    visible: bool = True

    def __post_init__(self) -> None:
        """Validate and normalize status bar item content."""

        if not isinstance(
            self.text,
            str,
        ):
            raise TypeError(
                "Status bar item text must be a string."
            )

        if (
            self.tooltip is not None
            and not isinstance(
                self.tooltip,
                str,
            )
        ):
            raise TypeError(
                "Status bar item tooltip must be a string or None."
            )

        if not isinstance(
            self.visible,
            bool,
        ):
            raise TypeError(
                "Status bar item visible flag must be a boolean."
            )


type StatusBarItemProvider = Callable[
    [],
    StatusBarItemContent,
]


@dataclass(frozen=True, slots=True, kw_only=True)
class StatusBarItemDefinition:
    """One registered status bar item and how to render its current state."""

    item_id: str
    alignment: StatusBarItemAlignment
    provider: StatusBarItemProvider
    order: int = 0

    def __post_init__(self) -> None:
        """Normalize and validate status bar item metadata."""

        object.__setattr__(
            self,
            "item_id",
            _require_non_empty_string(
                self.item_id,
                "Status bar item ID",
            ),
        )

        if not isinstance(
            self.alignment,
            StatusBarItemAlignment,
        ):
            raise TypeError(
                "Status bar item alignment must be "
                "StatusBarItemAlignment."
            )

        if not callable(
            self.provider,
        ):
            raise TypeError(
                "Status bar item provider must be callable."
            )

        if (
            not isinstance(
                self.order,
                int,
            )
            or isinstance(
                self.order,
                bool,
            )
        ):
            raise TypeError(
                "Status bar item order must be an integer."
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
