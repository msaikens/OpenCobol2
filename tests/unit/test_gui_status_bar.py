"""Unit tests for the status bar item renderer."""

from __future__ import annotations

from PySide6.QtWidgets import QStatusBar

from opencobol2.gui.status_bar import (
    build_status_bar,
    refresh_status_bar,
)
from opencobol2.services.status_bar import StatusBarService
from opencobol2.status_bar import (
    StatusBarItemAlignment,
    StatusBarItemContent,
    StatusBarItemDefinition,
    StatusBarItemRegistry,
)


def _build_service(
    text_holder: list,
) -> StatusBarService:
    registry = StatusBarItemRegistry()
    registry.register(
        StatusBarItemDefinition(
            item_id="left-item",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text=text_holder[0],
                tooltip="Left tooltip",
            ),
            order=10,
        )
    )
    registry.register(
        StatusBarItemDefinition(
            item_id="right-item",
            alignment=StatusBarItemAlignment.RIGHT,
            provider=lambda: StatusBarItemContent(
                text=text_holder[1],
            ),
            order=10,
        )
    )

    return StatusBarService(
        registry=registry,
    )


def test_build_status_bar_creates_one_label_per_item(
    qapp,
) -> None:
    service = _build_service(
        [
            "Left",
            "Right",
        ],
    )
    status_bar = QStatusBar()

    labels = build_status_bar(
        status_bar,
        service,
    )

    assert set(
        labels.keys(),
    ) == {
        "left-item",
        "right-item",
    }
    assert labels["left-item"].text() == "Left"
    assert labels["right-item"].text() == "Right"
    assert (
        labels["left-item"].toolTip()
        == "Left tooltip"
    )


def test_build_status_bar_places_items_by_alignment(
    qapp,
) -> None:
    service = _build_service(
        [
            "Left",
            "Right",
        ],
    )
    status_bar = QStatusBar()

    labels = build_status_bar(
        status_bar,
        service,
    )

    assert (
        labels["left-item"]
        in status_bar.children()
    )
    assert (
        labels["right-item"]
        in status_bar.children()
    )


def test_refresh_status_bar_updates_label_text(
    qapp,
) -> None:
    text_holder = [
        "Initial Left",
        "Initial Right",
    ]
    service = _build_service(
        text_holder,
    )
    status_bar = QStatusBar()
    labels = build_status_bar(
        status_bar,
        service,
    )

    text_holder[0] = "Updated Left"
    text_holder[1] = "Updated Right"
    refresh_status_bar(
        labels,
        service,
    )

    assert (
        labels["left-item"].text()
        == "Updated Left"
    )
    assert (
        labels["right-item"].text()
        == "Updated Right"
    )


def test_refresh_status_bar_applies_visibility(
    qapp,
) -> None:
    visible_holder = [True]
    registry = StatusBarItemRegistry()
    registry.register(
        StatusBarItemDefinition(
            item_id="toggle-item",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text="Toggle",
                visible=visible_holder[0],
            ),
        )
    )
    service = StatusBarService(
        registry=registry,
    )
    status_bar = QStatusBar()
    labels = build_status_bar(
        status_bar,
        service,
    )

    assert not labels["toggle-item"].isHidden()

    visible_holder[0] = False
    refresh_status_bar(
        labels,
        service,
    )

    assert labels["toggle-item"].isHidden()
