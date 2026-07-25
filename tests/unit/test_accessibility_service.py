"""Unit tests for accessibility profile orchestration."""

from __future__ import annotations

import pytest

from opencobol2.accessibility import (
    AccessibilityProfile,
    AccessibilityProfileRegistry,
    AccessibilitySettings,
    ToolWindowAccessibilityOverride,
)
from opencobol2.services.accessibility import (
    AccessibilityProfileActivationError,
    AccessibilityService,
)
from opencobol2.services.tool_windows import (
    ToolWindowService,
)
from opencobol2.tool_windows import (
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowRegistry,
)


def _create_tool_window_registry(
) -> ToolWindowRegistry:
    """Create tool-window definitions for accessibility tests."""

    registry = ToolWindowRegistry()

    registry.register(
        ToolWindowDefinition(
            tool_window_id="project-explorer",
            title="Project Explorer",
            default_area=ToolWindowArea.LEFT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
            ),
        )
    )
    registry.register(
        ToolWindowDefinition(
            tool_window_id="git-changes",
            title="Git Changes",
            default_area=ToolWindowArea.RIGHT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
                ToolWindowArea.BOTTOM,
                ToolWindowArea.DOCUMENT,
            ),
            default_visible=False,
            default_pinned=True,
        )
    )
    registry.register(
        ToolWindowDefinition(
            tool_window_id="fixed-window",
            title="Fixed Window",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.BOTTOM,
            ),
            supports_accent_color=False,
        )
    )

    return registry


def _create_service(
    *profiles: AccessibilityProfile,
) -> AccessibilityService:
    """Create accessibility orchestration for tests."""

    profile_registry = AccessibilityProfileRegistry()

    for profile in profiles:
        profile_registry.register(
            profile,
        )

    return AccessibilityService(
        profile_registry=profile_registry,
        tool_window_service=ToolWindowService(
            registry=_create_tool_window_registry(),
        ),
    )


def test_service_uses_neutral_settings_initially() -> None:
    service = _create_service()

    assert service.current_settings == AccessibilitySettings()
    assert service.active_profile_id is None
    assert service.active_profile is None


def test_activate_profile_applies_accessibility_settings() -> None:
    settings = AccessibilitySettings(
        editor_scale=1.25,
        reduce_motion=True,
        increase_focus_indicators=True,
        caret_width=3,
    )
    profile = AccessibilityProfile(
        name="Focus Coding",
        settings=settings,
    )

    service = _create_service(
        profile,
    )

    activated = service.activate_profile(
        profile.profile_id,
    )

    assert activated is profile
    assert service.current_settings is settings
    assert service.active_profile_id == profile.profile_id
    assert service.active_profile is profile


def test_activate_profile_applies_tool_window_overrides() -> None:
    profile = AccessibilityProfile(
        name="Focus Coding",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="git-changes",
                area=ToolWindowArea.LEFT,
                visible=True,
                pinned=False,
                override_accent_color=True,
                accent_color="#2F855A",
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    service.activate_profile(
        profile.profile_id,
    )

    state = service.tool_window_service.get_state(
        "git-changes",
    )

    assert state.area is ToolWindowArea.LEFT
    assert state.visible is True
    assert state.pinned is False
    assert state.auto_hide is True
    assert state.appearance.accent_color == "#2F855A"


def test_profile_can_explicitly_reset_tool_window_accent() -> None:
    profile = AccessibilityProfile(
        name="Default Window Colors",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="git-changes",
                override_accent_color=True,
                accent_color=None,
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    service.tool_window_service.set_accent_color(
        "git-changes",
        "#2F855A",
    )

    service.activate_profile(
        profile.profile_id,
    )

    state = service.tool_window_service.get_state(
        "git-changes",
    )

    assert state.appearance.uses_default_accent is True


def test_unspecified_tool_window_properties_are_preserved() -> None:
    profile = AccessibilityProfile(
        name="Color Only",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="git-changes",
                override_accent_color=True,
                accent_color="#805AD5",
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    service.tool_window_service.show(
        "git-changes",
    )
    service.tool_window_service.set_pinned(
        "git-changes",
        False,
    )

    service.activate_profile(
        profile.profile_id,
    )

    state = service.tool_window_service.get_state(
        "git-changes",
    )

    assert state.visible is True
    assert state.pinned is False
    assert state.appearance.accent_color == "#805AD5"


def test_manual_settings_update_clears_active_profile() -> None:
    profile = AccessibilityProfile(
        name="Focus Coding",
    )

    service = _create_service(
        profile,
    )

    service.activate_profile(
        profile.profile_id,
    )

    settings = AccessibilitySettings(
        interface_scale=1.5,
    )

    service.update_settings(
        settings,
    )

    assert service.current_settings is settings
    assert service.active_profile_id is None
    assert service.active_profile is None


def test_clear_active_profile_preserves_current_settings() -> None:
    settings = AccessibilitySettings(
        reduce_motion=True,
    )
    profile = AccessibilityProfile(
        name="Focus Coding",
        settings=settings,
    )

    service = _create_service(
        profile,
    )

    service.activate_profile(
        profile.profile_id,
    )
    service.clear_active_profile()

    assert service.current_settings is settings
    assert service.active_profile_id is None


def test_profile_is_validated_before_any_window_override_is_applied() -> None:
    profile = AccessibilityProfile(
        name="Invalid Layout",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="git-changes",
                visible=True,
                override_accent_color=True,
                accent_color="#2F855A",
            ),
            ToolWindowAccessibilityOverride(
                tool_window_id="project-explorer",
                area=ToolWindowArea.BOTTOM,
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    with pytest.raises(
        AccessibilityProfileActivationError,
        match="disallowed tool-window area",
    ):
        service.activate_profile(
            profile.profile_id,
        )

    git_state = service.tool_window_service.get_state(
        "git-changes",
    )

    assert git_state.visible is False
    assert git_state.appearance.uses_default_accent is True
    assert service.active_profile_id is None


def test_profile_rejects_accent_override_for_unsupported_window() -> None:
    profile = AccessibilityProfile(
        name="Invalid Accent",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="fixed-window",
                override_accent_color=True,
                accent_color="#112233",
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    with pytest.raises(
        AccessibilityProfileActivationError,
        match="does not support custom accents",
    ):
        service.activate_profile(
            profile.profile_id,
        )


def test_activate_profile_wraps_stale_tool_window_id() -> None:
    """A profile referencing an unregistered tool_window_id must raise
    AccessibilityProfileActivationError, not let ToolWindowNotFoundError
    leak out of the tool-window service's exception hierarchy."""

    profile = AccessibilityProfile(
        name="Stale Reference",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="does-not-exist",
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    with pytest.raises(
        AccessibilityProfileActivationError,
    ):
        service.activate_profile(
            profile.profile_id,
        )

    assert service.active_profile_id is None


def test_activate_profile_wraps_floating_document_area_conflict() -> None:
    """A profile that would move a currently-floating tool window into
    the document area hits ToolWindowService's own floating/DOCUMENT
    conflict guard -- that ValueError must surface as
    AccessibilityProfileActivationError, the one error type callers of
    activate_profile need to handle."""

    profile = AccessibilityProfile(
        name="Conflicting Layout",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="git-changes",
                area=ToolWindowArea.DOCUMENT,
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    service.tool_window_service.set_floating(
        "git-changes",
        True,
    )

    with pytest.raises(
        AccessibilityProfileActivationError,
    ):
        service.activate_profile(
            profile.profile_id,
        )

    assert service.active_profile_id is None


def test_profile_rejects_auto_hide_for_currently_floating_window() -> None:
    profile = AccessibilityProfile(
        name="Invalid Auto Hide",
        tool_window_overrides=(
            ToolWindowAccessibilityOverride(
                tool_window_id="git-changes",
                pinned=False,
            ),
        ),
    )

    service = _create_service(
        profile,
    )

    service.tool_window_service.set_floating(
        "git-changes",
        True,
    )

    with pytest.raises(
        AccessibilityProfileActivationError,
        match="cannot auto-hide a floating tool window",
    ):
        service.activate_profile(
            profile.profile_id,
        )