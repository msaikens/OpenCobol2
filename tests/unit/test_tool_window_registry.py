"""Unit tests for IDE tool-window registration."""

from __future__ import annotations

import pytest

from opencobol2.tool_windows import (
    ToolWindowAlreadyRegisteredError,
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowNotFoundError,
    ToolWindowRegistry,
)


def _create_definition(
    tool_window_id: str,
) -> ToolWindowDefinition:
    """Create a simple tool-window definition."""

    return ToolWindowDefinition(
        tool_window_id=tool_window_id,
        title=tool_window_id,
        default_area=ToolWindowArea.BOTTOM,
        allowed_areas=(
            ToolWindowArea.BOTTOM,
        ),
    )


def test_registry_preserves_registration_order() -> None:
    registry = ToolWindowRegistry()

    first = _create_definition(
        "output",
    )
    second = _create_definition(
        "problems",
    )

    registry.register(
        first,
    )
    registry.register(
        second,
    )

    assert registry.definitions == (
        first,
        second,
    )


def test_registry_get_returns_definition() -> None:
    registry = ToolWindowRegistry()
    definition = _create_definition(
        "output",
    )

    registry.register(
        definition,
    )

    assert registry.get(
        "output",
    ) is definition


def test_registry_rejects_duplicate_tool_window_id() -> None:
    registry = ToolWindowRegistry()

    registry.register(
        _create_definition(
            "output",
        )
    )

    with pytest.raises(
        ToolWindowAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(
            _create_definition(
                "output",
            )
        )


def test_registry_unregister_returns_definition() -> None:
    registry = ToolWindowRegistry()
    definition = _create_definition(
        "output",
    )

    registry.register(
        definition,
    )

    removed = registry.unregister(
        "output",
    )

    assert removed is definition
    assert registry.contains(
        "output",
    ) is False


def test_registry_rejects_unknown_tool_window() -> None:
    registry = ToolWindowRegistry()

    with pytest.raises(
        ToolWindowNotFoundError,
        match="is not registered",
    ):
        registry.get(
            "missing",
        )


def test_registry_requires_definition_instances() -> None:
    registry = ToolWindowRegistry()

    with pytest.raises(
        TypeError,
        match="ToolWindowDefinition instances",
    ):
        registry.register(
            "output",  # type: ignore[arg-type]
        )