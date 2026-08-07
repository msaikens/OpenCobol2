"""IDE tool-window shell state orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from opencobol2.tool_windows import (
    ToolWindowAppearance,
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowGeometry,
    ToolWindowRegistry,
    ToolWindowState,
)


class ToolWindowAreaNotAllowedError(
    ValueError,
):
    """Raised when a tool window cannot use a requested area."""


class ToolWindowAccentNotSupportedError(
    ValueError,
):
    """Raised when a tool window does not support custom accents."""


class ToolWindowService:
    """Manages live IDE tool-window shell state."""

    def __init__(
        self,
        *,
        registry: ToolWindowRegistry,
    ) -> None:
        """Initialize tool-window shell state management."""

        if not isinstance(
            registry,
            ToolWindowRegistry,
        ):
            raise TypeError(
                "Tool-window service registry must be "
                "ToolWindowRegistry."
            )

        self._registry = registry
        self._states: dict[
            str,
            ToolWindowState,
        ] = {}
        self._listeners: list[
            Callable[[ToolWindowState], None]
        ] = []

    def add_listener(
        self,
        callback: Callable[[ToolWindowState], None],
    ) -> None:
        """Register a callback invoked with the new state after every change.

        Editor §UIShell-1: this is what lets a real Qt dock widget stay in
        sync with `activate()`/`show()`/`hide()` calls that don't originate
        from the dock widget itself (e.g. a View-menu command) -- until
        this existed, nothing synced domain-state changes back onto the
        real `QDockWidget` at all, only the reverse direction (dock ->
        service, via `visibilityChanged`).
        """

        self._listeners.append(
            callback,
        )

    @property
    def registry(
        self,
    ) -> ToolWindowRegistry:
        """Return the tool-window definition registry."""

        return self._registry

    @property
    def states(
        self,
    ) -> tuple[ToolWindowState, ...]:
        """Return current state for every registered tool window."""

        return tuple(
            self.get_state(
                definition.tool_window_id,
            )
            for definition in self._registry.definitions
        )

    def get_state(
        self,
        tool_window_id: str,
    ) -> ToolWindowState:
        """Return current state for one tool window."""

        definition = self._registry.get(
            tool_window_id,
        )

        state = self._states.get(
            definition.tool_window_id,
        )

        if state is None:
            state = _create_default_state(
                definition,
            )
            self._states[
                definition.tool_window_id
            ] = state

        return state

    def show(
        self,
        tool_window_id: str,
    ) -> ToolWindowState:
        """Show a tool window without changing activation."""

        return self._store(
            replace(
                self.get_state(
                    tool_window_id,
                ),
                visible=True,
            )
        )

    def hide(
        self,
        tool_window_id: str,
    ) -> ToolWindowState:
        """Hide a tool window."""

        return self._store(
            replace(
                self.get_state(
                    tool_window_id,
                ),
                visible=False,
                active=False,
            )
        )

    def activate(
        self,
        tool_window_id: str,
    ) -> ToolWindowState:
        """Show and activate one tool window."""

        target_state = self.get_state(
            tool_window_id,
        )

        for state in self.states:
            if (
                state.tool_window_id
                != target_state.tool_window_id
                and state.active
            ):
                self._store(
                    replace(
                        state,
                        active=False,
                    )
                )

        return self._store(
            replace(
                target_state,
                visible=True,
                active=True,
            )
        )

    def set_pinned(
        self,
        tool_window_id: str,
        pinned: bool,
    ) -> ToolWindowState:
        """Set pinned or auto-hide behavior for a tool window."""

        if not isinstance(
            pinned,
            bool,
        ):
            raise TypeError(
                "Tool-window pinned state must be a boolean."
            )

        state = self.get_state(
            tool_window_id,
        )

        if (
            not pinned
            and (
                state.floating
                or state.area is ToolWindowArea.DOCUMENT
            )
        ):
            raise ValueError(
                "Floating and document-area tool windows "
                "cannot use auto-hide."
            )

        return self._store(
            replace(
                state,
                pinned=pinned,
            )
        )

    def set_floating(
        self,
        tool_window_id: str,
        floating: bool,
    ) -> ToolWindowState:
        """Set whether a tool window is floating."""

        if not isinstance(
            floating,
            bool,
        ):
            raise TypeError(
                "Tool-window floating state must be a boolean."
            )

        state = self.get_state(
            tool_window_id,
        )

        if (
            floating
            and state.area is ToolWindowArea.DOCUMENT
        ):
            # DOCUMENT area means "pinned like an editor tab";
            # floating means "detached into its own top-level window".
            # Allowing both at once produces a shell state no renderer
            # branch is written to handle.
            raise ValueError(
                "A document-area tool window cannot be made "
                f"floating: {tool_window_id!r}."
            )

        return self._store(
            replace(
                state,
                floating=floating,
                pinned=(
                    True
                    if floating
                    else state.pinned
                ),
            )
        )

    def move_to_area(
        self,
        tool_window_id: str,
        area: ToolWindowArea,
    ) -> ToolWindowState:
        """Move a tool window to an allowed shell area."""

        if not isinstance(
            area,
            ToolWindowArea,
        ):
            raise TypeError(
                "Tool-window area must be ToolWindowArea."
            )

        definition = self._registry.get(
            tool_window_id,
        )

        if area not in definition.allowed_areas:
            raise ToolWindowAreaNotAllowedError(
                "Tool window does not allow area "
                f"{area.value!r}: "
                f"{definition.tool_window_id!r}."
            )

        state = self.get_state(
            tool_window_id,
        )

        if (
            area is ToolWindowArea.DOCUMENT
            and state.floating
        ):
            # See the matching check in set_floating(): a floating,
            # document-area tool window is a combination no renderer
            # branch is written to handle.
            raise ValueError(
                "A floating tool window cannot be moved to the "
                f"document area: {tool_window_id!r}."
            )

        return self._store(
            replace(
                state,
                area=area,
                pinned=(
                    True
                    if area is ToolWindowArea.DOCUMENT
                    else state.pinned
                ),
            )
        )

    def set_accent_color(
        self,
        tool_window_id: str,
        accent_color: str,
    ) -> ToolWindowState:
        """Set a custom accent color for one tool window."""

        definition = self._registry.get(
            tool_window_id,
        )

        if not definition.supports_accent_color:
            raise ToolWindowAccentNotSupportedError(
                "Tool window does not support a custom accent: "
                f"{definition.tool_window_id!r}."
            )

        state = self.get_state(
            tool_window_id,
        )

        return self._store(
            replace(
                state,
                appearance=ToolWindowAppearance(
                    accent_color=accent_color,
                ),
            )
        )

    def reset_accent_color(
        self,
        tool_window_id: str,
    ) -> ToolWindowState:
        """Restore the application-default tool-window accent."""

        state = self.get_state(
            tool_window_id,
        )

        return self._store(
            replace(
                state,
                appearance=ToolWindowAppearance(),
            )
        )

    def set_geometry(
        self,
        tool_window_id: str,
        geometry: ToolWindowGeometry | None,
    ) -> ToolWindowState:
        """Set persisted floating-window geometry."""

        if (
            geometry is not None
            and not isinstance(
                geometry,
                ToolWindowGeometry,
            )
        ):
            raise TypeError(
                "Tool-window geometry must be "
                "ToolWindowGeometry."
            )

        return self._store(
            replace(
                self.get_state(
                    tool_window_id,
                ),
                geometry=geometry,
            )
        )

    def set_tab_group(
        self,
        tool_window_id: str,
        tab_group_id: str | None,
    ) -> ToolWindowState:
        """Set the shell tab group for one tool window."""

        return self._store(
            replace(
                self.get_state(
                    tool_window_id,
                ),
                tab_group_id=tab_group_id,
            )
        )

    def _store(
        self,
        state: ToolWindowState,
    ) -> ToolWindowState:
        """Store one validated tool-window state and notify listeners."""

        self._registry.get(
            state.tool_window_id,
        )

        self._states[
            state.tool_window_id
        ] = state

        for listener in self._listeners:
            try:
                listener(
                    state,
                )
            except Exception:
                pass

        return state


def _create_default_state(
    definition: ToolWindowDefinition,
) -> ToolWindowState:
    """Create initial shell state from a tool-window definition."""

    return ToolWindowState(
        tool_window_id=definition.tool_window_id,
        area=definition.default_area,
        visible=definition.default_visible,
        pinned=definition.default_pinned,
    )