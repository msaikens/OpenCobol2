"""Registration of IDE tool-window definitions."""

from __future__ import annotations

from opencobol2.tool_windows.models import (
    ToolWindowDefinition,
)


class ToolWindowAlreadyRegisteredError(
    ValueError,
):
    """Raised when a tool-window ID is already registered."""


class ToolWindowNotFoundError(
    LookupError,
):
    """Raised when a tool-window ID is not registered."""


class ToolWindowRegistry:
    """Ordered registry of IDE tool-window definitions."""

    def __init__(
        self,
    ) -> None:
        """Initialize an empty tool-window registry."""

        self._definitions: dict[
            str,
            ToolWindowDefinition,
        ] = {}

    @property
    def definitions(
        self,
    ) -> tuple[ToolWindowDefinition, ...]:
        """Return definitions in registration order."""

        return tuple(
            self._definitions.values(),
        )

    def register(
        self,
        definition: ToolWindowDefinition,
    ) -> None:
        """Register one tool-window definition."""

        if not isinstance(
            definition,
            ToolWindowDefinition,
        ):
            raise TypeError(
                "Tool-window registry entries must be "
                "ToolWindowDefinition instances."
            )

        if (
            definition.tool_window_id
            in self._definitions
        ):
            raise ToolWindowAlreadyRegisteredError(
                "Tool window is already registered: "
                f"{definition.tool_window_id!r}."
            )

        self._definitions[
            definition.tool_window_id
        ] = definition

    def unregister(
        self,
        tool_window_id: str,
    ) -> ToolWindowDefinition:
        """Remove and return one tool-window definition."""

        normalized_tool_window_id = (
            _normalize_tool_window_id(
                tool_window_id,
            )
        )

        try:
            return self._definitions.pop(
                normalized_tool_window_id,
            )
        except KeyError as error:
            raise ToolWindowNotFoundError(
                "Tool window is not registered: "
                f"{normalized_tool_window_id!r}."
            ) from error

    def get(
        self,
        tool_window_id: str,
    ) -> ToolWindowDefinition:
        """Return one registered tool-window definition."""

        normalized_tool_window_id = (
            _normalize_tool_window_id(
                tool_window_id,
            )
        )

        try:
            return self._definitions[
                normalized_tool_window_id
            ]
        except KeyError as error:
            raise ToolWindowNotFoundError(
                "Tool window is not registered: "
                f"{normalized_tool_window_id!r}."
            ) from error

    def contains(
        self,
        tool_window_id: str,
    ) -> bool:
        """Return whether a tool-window ID is registered."""

        normalized_tool_window_id = (
            _normalize_tool_window_id(
                tool_window_id,
            )
        )

        return (
            normalized_tool_window_id
            in self._definitions
        )


def _normalize_tool_window_id(
    tool_window_id: str,
) -> str:
    """Normalize and validate a tool-window identifier."""

    if not isinstance(
        tool_window_id,
        str,
    ):
        raise TypeError(
            "Tool-window ID must be a string."
        )

    normalized_tool_window_id = (
        tool_window_id.strip()
    )

    if not normalized_tool_window_id:
        raise ValueError(
            "Tool-window ID must not be empty."
        )

    return normalized_tool_window_id