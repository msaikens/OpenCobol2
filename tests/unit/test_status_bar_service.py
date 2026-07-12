"""Unit tests for status bar item resolution."""

from __future__ import annotations

import pytest

from opencobol2.services.status_bar import (
    ResolvedStatusBarItem,
    StatusBarService,
)
from opencobol2.status_bar import (
    StatusBarItemAlignment,
    StatusBarItemContent,
    StatusBarItemDefinition,
    StatusBarItemRegistry,
)


def test_resolve_item_calls_provider_for_current_content() -> None:
    registry = StatusBarItemRegistry()
    calls = []

    def provider() -> StatusBarItemContent:
        calls.append(1)
        return StatusBarItemContent(
            text=f"call-{len(calls)}",
        )

    registry.register(
        StatusBarItemDefinition(
            item_id="counter",
            alignment=StatusBarItemAlignment.LEFT,
            provider=provider,
        )
    )
    service = StatusBarService(
        registry=registry,
    )

    first = service.resolve_item(
        "counter",
    )
    second = service.resolve_item(
        "counter",
    )

    assert first.content.text == "call-1"
    assert second.content.text == "call-2"
    assert isinstance(
        first,
        ResolvedStatusBarItem,
    )


def test_resolve_alignment_resolves_every_matching_item_in_order() -> None:
    registry = StatusBarItemRegistry()
    registry.register(
        StatusBarItemDefinition(
            item_id="b",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text="B",
            ),
            order=20,
        )
    )
    registry.register(
        StatusBarItemDefinition(
            item_id="a",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text="A",
            ),
            order=10,
        )
    )
    service = StatusBarService(
        registry=registry,
    )

    resolved = service.resolve_alignment(
        StatusBarItemAlignment.LEFT,
    )

    assert [
        item.content.text for item in resolved
    ] == [
        "A",
        "B",
    ]


def test_service_requires_status_bar_item_registry() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Status bar service registry must be "
            "StatusBarItemRegistry"
        ),
    ):
        StatusBarService(
            registry=object(),  # type: ignore[arg-type]
        )
