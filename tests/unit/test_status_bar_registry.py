"""Unit tests for the status bar item registry."""

from __future__ import annotations

import pytest

from opencobol2.status_bar import (
    StatusBarItemAlignment,
    StatusBarItemAlreadyRegisteredError,
    StatusBarItemContent,
    StatusBarItemDefinition,
    StatusBarItemNotFoundError,
    StatusBarItemRegistry,
)


def _create_item(
    item_id: str,
    alignment: StatusBarItemAlignment = StatusBarItemAlignment.LEFT,
    order: int = 0,
) -> StatusBarItemDefinition:
    return StatusBarItemDefinition(
        item_id=item_id,
        alignment=alignment,
        provider=lambda: StatusBarItemContent(
            text=item_id,
        ),
        order=order,
    )


def test_registry_starts_empty() -> None:
    registry = StatusBarItemRegistry()

    assert registry.items == ()


def test_registry_registers_and_returns_item() -> None:
    registry = StatusBarItemRegistry()
    item = _create_item("project")

    registry.register(item)

    assert registry.get("project") is item
    assert registry.items == (item,)


def test_registry_rejects_duplicate_id() -> None:
    registry = StatusBarItemRegistry()
    registry.register(
        _create_item("project"),
    )

    with pytest.raises(
        StatusBarItemAlreadyRegisteredError,
        match="project",
    ):
        registry.register(
            _create_item("project"),
        )


def test_registry_raises_for_unknown_item() -> None:
    registry = StatusBarItemRegistry()

    with pytest.raises(
        StatusBarItemNotFoundError,
        match="unknown",
    ):
        registry.get("unknown")


def test_registry_rejects_non_definition_registration() -> None:
    registry = StatusBarItemRegistry()

    with pytest.raises(
        TypeError,
        match=(
            "Registered status bar item must be "
            "StatusBarItemDefinition"
        ),
    ):
        registry.register(
            object(),  # type: ignore[arg-type]
        )


def test_for_alignment_returns_matching_items_sorted_by_order() -> None:
    registry = StatusBarItemRegistry()
    registry.register(
        _create_item(
            "b",
            StatusBarItemAlignment.LEFT,
            order=20,
        )
    )
    registry.register(
        _create_item(
            "a",
            StatusBarItemAlignment.LEFT,
            order=10,
        )
    )
    registry.register(
        _create_item(
            "right-item",
            StatusBarItemAlignment.RIGHT,
            order=5,
        )
    )

    left_items = registry.for_alignment(
        StatusBarItemAlignment.LEFT,
    )
    right_items = registry.for_alignment(
        StatusBarItemAlignment.RIGHT,
    )

    assert [
        item.item_id for item in left_items
    ] == [
        "a",
        "b",
    ]
    assert [
        item.item_id for item in right_items
    ] == ["right-item"]


def test_for_alignment_rejects_non_enum_alignment() -> None:
    registry = StatusBarItemRegistry()

    with pytest.raises(
        TypeError,
        match=(
            "Status bar item alignment must be "
            "StatusBarItemAlignment"
        ),
    ):
        registry.for_alignment(
            "left",  # type: ignore[arg-type]
        )
