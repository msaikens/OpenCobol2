"""Accessibility profile and working-environment orchestration."""

from __future__ import annotations

from uuid import UUID

from opencobol2.accessibility import (
    AccessibilityProfile,
    AccessibilityProfileRegistry,
    AccessibilitySettings,
    ToolWindowAccessibilityOverride,
)
from opencobol2.services.tool_windows import (
    ToolWindowAccentNotSupportedError,
    ToolWindowAreaNotAllowedError,
    ToolWindowService,
)
from opencobol2.tool_windows import (
    ToolWindowArea,
)


class AccessibilityProfileActivationError(
    ValueError,
):
    """Raised when an accessibility profile cannot be applied."""


class AccessibilityService:
    """Manages active accessibility preferences and profiles."""

    def __init__(
        self,
        *,
        profile_registry: AccessibilityProfileRegistry,
        tool_window_service: ToolWindowService,
        initial_settings: AccessibilitySettings | None = None,
    ) -> None:
        """Initialize accessibility orchestration."""

        if not isinstance(
            profile_registry,
            AccessibilityProfileRegistry,
        ):
            raise TypeError(
                "Accessibility service profile registry must be "
                "AccessibilityProfileRegistry."
            )

        if not isinstance(
            tool_window_service,
            ToolWindowService,
        ):
            raise TypeError(
                "Accessibility service tool-window service must be "
                "ToolWindowService."
            )

        if (
            initial_settings is not None
            and not isinstance(
                initial_settings,
                AccessibilitySettings,
            )
        ):
            raise TypeError(
                "Initial accessibility settings must be "
                "AccessibilitySettings."
            )

        self._profile_registry = profile_registry
        self._tool_window_service = tool_window_service
        self._current_settings = (
            AccessibilitySettings()
            if initial_settings is None
            else initial_settings
        )
        self._active_profile_id: UUID | None = None

    @property
    def profile_registry(
        self,
    ) -> AccessibilityProfileRegistry:
        """Return the accessibility profile registry."""

        return self._profile_registry

    @property
    def tool_window_service(
        self,
    ) -> ToolWindowService:
        """Return the IDE tool-window service."""

        return self._tool_window_service

    @property
    def current_settings(
        self,
    ) -> AccessibilitySettings:
        """Return the currently active accessibility settings."""

        return self._current_settings

    @property
    def active_profile_id(
        self,
    ) -> UUID | None:
        """Return the active accessibility profile identifier."""

        return self._active_profile_id

    @property
    def active_profile(
        self,
    ) -> AccessibilityProfile | None:
        """Return the active accessibility profile."""

        if self._active_profile_id is None:
            return None

        return self._profile_registry.get(
            self._active_profile_id,
        )

    def update_settings(
        self,
        settings: AccessibilitySettings,
    ) -> AccessibilitySettings:
        """Apply accessibility settings without selecting a profile."""

        if not isinstance(
            settings,
            AccessibilitySettings,
        ):
            raise TypeError(
                "Accessibility settings must be "
                "AccessibilitySettings."
            )

        self._current_settings = settings
        self._active_profile_id = None

        return settings

    def activate_profile(
        self,
        profile_id: UUID,
    ) -> AccessibilityProfile:
        """Activate a named accessibility profile."""

        profile = self._profile_registry.get(
            profile_id,
        )

        self._validate_profile_activation(
            profile,
        )

        for override in profile.tool_window_overrides:
            self._apply_tool_window_override(
                override,
            )

        self._current_settings = profile.settings
        self._active_profile_id = profile.profile_id

        return profile

    def clear_active_profile(
        self,
    ) -> None:
        """Clear profile selection without changing current settings."""

        self._active_profile_id = None

    def _validate_profile_activation(
        self,
        profile: AccessibilityProfile,
    ) -> None:
        """Validate all shell overrides before applying a profile."""

        for override in profile.tool_window_overrides:
            definition = (
                self._tool_window_service.registry.get(
                    override.tool_window_id,
                )
            )
            state = self._tool_window_service.get_state(
                override.tool_window_id,
            )

            if (
                override.area is not None
                and override.area not in definition.allowed_areas
            ):
                raise AccessibilityProfileActivationError(
                    "Accessibility profile requests a disallowed "
                    "tool-window area "
                    f"{override.area.value!r} for "
                    f"{override.tool_window_id!r}."
                )

            effective_area = (
                state.area
                if override.area is None
                else override.area
            )

            if (
                effective_area is ToolWindowArea.DOCUMENT
                and override.pinned is False
            ):
                raise AccessibilityProfileActivationError(
                    "Accessibility profile cannot auto-hide "
                    "a document-area tool window: "
                    f"{override.tool_window_id!r}."
                )

            if (
                state.floating
                and override.pinned is False
            ):
                raise AccessibilityProfileActivationError(
                    "Accessibility profile cannot auto-hide "
                    "a floating tool window: "
                    f"{override.tool_window_id!r}."
                )

            if (
                override.override_accent_color
                and not definition.supports_accent_color
            ):
                raise AccessibilityProfileActivationError(
                    "Accessibility profile requests an accent "
                    "override for a tool window that does not "
                    "support custom accents: "
                    f"{override.tool_window_id!r}."
                )

    def _apply_tool_window_override(
        self,
        override: ToolWindowAccessibilityOverride,
    ) -> None:
        """Apply one validated tool-window profile override."""

        tool_window_id = override.tool_window_id

        if override.area is not None:
            self._tool_window_service.move_to_area(
                tool_window_id,
                override.area,
            )

        if override.pinned is not None:
            self._tool_window_service.set_pinned(
                tool_window_id,
                override.pinned,
            )

        if override.override_accent_color:
            if override.accent_color is None:
                self._tool_window_service.reset_accent_color(
                    tool_window_id,
                )
            else:
                self._tool_window_service.set_accent_color(
                    tool_window_id,
                    override.accent_color,
                )

        if override.visible is True:
            self._tool_window_service.show(
                tool_window_id,
            )
        elif override.visible is False:
            self._tool_window_service.hide(
                tool_window_id,
            )