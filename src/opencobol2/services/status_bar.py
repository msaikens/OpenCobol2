"""Status bar item resolution against live application state."""

from __future__ import annotations

from dataclasses import dataclass

from opencobol2.status_bar import (
    StatusBarItemAlignment,
    StatusBarItemContent,
    StatusBarItemDefinition,
    StatusBarItemRegistry,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedStatusBarItem:
    """A status bar item paired with its current, provider-resolved content."""

    definition: StatusBarItemDefinition
    content: StatusBarItemContent

    def __post_init__(self) -> None:
        """Validate a resolved status bar item."""

        if not isinstance(
            self.definition,
            StatusBarItemDefinition,
        ):
            raise TypeError(
                "Resolved status bar item definition must be "
                "StatusBarItemDefinition."
            )

        if not isinstance(
            self.content,
            StatusBarItemContent,
        ):
            raise TypeError(
                "Resolved status bar item content must be "
                "StatusBarItemContent."
            )


class StatusBarService:
    """Resolves registered status bar items to their current content."""

    def __init__(
        self,
        *,
        registry: StatusBarItemRegistry,
    ) -> None:
        """Initialize status bar item resolution."""

        if not isinstance(
            registry,
            StatusBarItemRegistry,
        ):
            raise TypeError(
                "Status bar service registry must be "
                "StatusBarItemRegistry."
            )

        self._registry = registry

    @property
    def registry(
        self,
    ) -> StatusBarItemRegistry:
        """Return the underlying status bar item registry."""

        return self._registry

    def resolve_item(
        self,
        item_id: str,
    ) -> ResolvedStatusBarItem:
        """Resolve one status bar item's current content."""

        definition = self._registry.get(
            item_id,
        )

        return ResolvedStatusBarItem(
            definition=definition,
            content=definition.provider(),
        )

    def resolve_alignment(
        self,
        alignment: StatusBarItemAlignment,
    ) -> tuple[ResolvedStatusBarItem, ...]:
        """Resolve every item in one alignment group, in display order."""

        return tuple(
            ResolvedStatusBarItem(
                definition=definition,
                content=definition.provider(),
            )
            for definition in self._registry.for_alignment(
                alignment,
            )
        )
