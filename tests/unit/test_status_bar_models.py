"""Unit tests for status bar item domain models."""

from __future__ import annotations

import pytest

from opencobol2.status_bar import (
    StatusBarItemAlignment,
    StatusBarItemContent,
    StatusBarItemDefinition,
)


def test_status_bar_item_content_defaults() -> None:
    content = StatusBarItemContent(
        text="Ready",
    )

    assert content.text == "Ready"
    assert content.tooltip is None
    assert content.visible is True


def test_status_bar_item_content_rejects_non_string_text() -> None:
    with pytest.raises(
        TypeError,
        match="Status bar item text must be a string",
    ):
        StatusBarItemContent(
            text=1,  # type: ignore[arg-type]
        )


def test_status_bar_item_content_rejects_non_boolean_visible() -> None:
    with pytest.raises(
        TypeError,
        match="Status bar item visible flag must be a boolean",
    ):
        StatusBarItemContent(
            text="Ready",
            visible="yes",  # type: ignore[arg-type]
        )


def test_status_bar_item_definition_requires_non_empty_id() -> None:
    with pytest.raises(
        ValueError,
        match="Status bar item ID must not be empty",
    ):
        StatusBarItemDefinition(
            item_id="   ",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text="x",
            ),
        )


def test_status_bar_item_definition_requires_alignment_enum() -> None:
    with pytest.raises(
        TypeError,
        match=(
            "Status bar item alignment must be "
            "StatusBarItemAlignment"
        ),
    ):
        StatusBarItemDefinition(
            item_id="demo",
            alignment="left",  # type: ignore[arg-type]
            provider=lambda: StatusBarItemContent(
                text="x",
            ),
        )


def test_status_bar_item_definition_requires_callable_provider() -> None:
    with pytest.raises(
        TypeError,
        match="Status bar item provider must be callable",
    ):
        StatusBarItemDefinition(
            item_id="demo",
            alignment=StatusBarItemAlignment.LEFT,
            provider="not callable",  # type: ignore[arg-type]
        )


def test_status_bar_item_definition_rejects_non_integer_order() -> None:
    with pytest.raises(
        TypeError,
        match="Status bar item order must be an integer",
    ):
        StatusBarItemDefinition(
            item_id="demo",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text="x",
            ),
            order=1.5,  # type: ignore[arg-type]
        )
