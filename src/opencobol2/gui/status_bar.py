"""Renders status bar item contributions as live Qt status bar labels."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QStatusBar,
)

from opencobol2.services.status_bar import StatusBarService
from opencobol2.status_bar import StatusBarItemAlignment


def build_status_bar(
    status_bar: QStatusBar,
    service: StatusBarService,
) -> dict[str, QLabel]:
    """Create one label per registered status bar item and populate it."""

    labels: dict[str, QLabel] = {}

    for definition in service.registry.for_alignment(
        StatusBarItemAlignment.LEFT,
    ):
        label = QLabel()
        status_bar.addWidget(
            label,
        )
        labels[definition.item_id] = label

    for definition in service.registry.for_alignment(
        StatusBarItemAlignment.RIGHT,
    ):
        label = QLabel()
        status_bar.addPermanentWidget(
            label,
        )
        labels[definition.item_id] = label

    refresh_status_bar(
        labels,
        service,
    )

    return labels


def refresh_status_bar(
    labels: dict[str, QLabel],
    service: StatusBarService,
) -> None:
    """Refresh every label from its item's current provider content."""

    for item_id, label in labels.items():
        resolved = service.resolve_item(
            item_id,
        )
        label.setText(
            resolved.content.text,
        )
        label.setToolTip(
            resolved.content.tooltip or "",
        )
        label.setVisible(
            resolved.content.visible,
        )
