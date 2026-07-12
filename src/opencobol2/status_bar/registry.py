"""Status bar item registration and lookup."""

from __future__ import annotations

from opencobol2.status_bar.models import (
    StatusBarItemAlignment,
    StatusBarItemDefinition,
)


class StatusBarItemAlreadyRegisteredError(ValueError):
    """Raised when a status bar item ID is already registered."""


class StatusBarItemNotFoundError(LookupError):
    """Raised when a requested status bar item is unknown."""


class StatusBarItemRegistry:
    """Registers status bar items and resolves them by ID or alignment."""

    __slots__ = (
        "_items",
    )

    def __init__(self) -> None:
        self._items: dict[
            str,
            StatusBarItemDefinition,
        ] = {}

    @property
    def items(
        self,
    ) -> tuple[StatusBarItemDefinition, ...]:
        """Return registered items in registration order."""

        return tuple(
            self._items.values()
        )

    def register(
        self,
        item: StatusBarItemDefinition,
    ) -> None:
        """Register one status bar item."""

        if not isinstance(
            item,
            StatusBarItemDefinition,
        ):
            raise TypeError(
                "Registered status bar item must be "
                "StatusBarItemDefinition."
            )

        if item.item_id in self._items:
            raise StatusBarItemAlreadyRegisteredError(
                "Status bar item is already registered: "
                f"{item.item_id}"
            )

        self._items[
            item.item_id
        ] = item

    def get(
        self,
        item_id: str,
    ) -> StatusBarItemDefinition:
        """Return a registered status bar item by ID."""

        try:
            return self._items[
                item_id
            ]
        except KeyError:
            raise StatusBarItemNotFoundError(
                f"Status bar item is not registered: {item_id}"
            ) from None

    def for_alignment(
        self,
        alignment: StatusBarItemAlignment,
    ) -> tuple[StatusBarItemDefinition, ...]:
        """Return items for one alignment group, ordered for display."""

        if not isinstance(
            alignment,
            StatusBarItemAlignment,
        ):
            raise TypeError(
                "Status bar item alignment must be "
                "StatusBarItemAlignment."
            )

        matching_items = tuple(
            item
            for item in self._items.values()
            if item.alignment is alignment
        )

        return tuple(
            sorted(
                matching_items,
                key=lambda item: item.order,
            )
        )
