"""Unit tests for accessibility domain models."""

from __future__ import annotations

from uuid import UUID

import pytest

from opencobol2.accessibility import (
    AccessibilityProfile,
    AccessibilitySettings,
    ColorVisionAssistance,
    ToolWindowAccessibilityOverride,
)
from opencobol2.tool_windows import (
    ToolWindowArea,
)


def test_accessibility_settings_have_neutral_defaults() -> None:
    settings = AccessibilitySettings()

    assert settings.interface_scale == 1.0
    assert settings.editor_scale == 1.0
    assert settings.high_contrast is False
    assert settings.reduce_motion is False
    assert settings.reduce_visual_effects is False
    assert settings.increase_focus_indicators is False
    assert settings.always_show_mnemonics is False
    assert settings.screen_reader_optimizations is False
    assert (
        settings.color_vision_assistance
        is ColorVisionAssistance.OFF
    )
    assert settings.caret_width == 1
    assert settings.minimum_control_size == 0


def test_accessibility_scales_are_normalized_to_floats() -> None:
    settings = AccessibilitySettings(
        interface_scale=2,
        editor_scale=3,
    )

    assert settings.interface_scale == 2.0
    assert settings.editor_scale == 3.0
    assert isinstance(
        settings.interface_scale,
        float,
    )
    assert isinstance(
        settings.editor_scale,
        float,
    )


@pytest.mark.parametrize(
    "scale",
    [
        0.49,
        4.01,
        0,
        10,
    ],
)
def test_accessibility_scale_outside_supported_range_is_rejected(
    scale: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0.5 and 4.0",
    ):
        AccessibilitySettings(
            interface_scale=scale,
        )


def test_caret_width_has_bounded_range() -> None:
    with pytest.raises(
        ValueError,
        match="caret width must be between 1 and 10",
    ):
        AccessibilitySettings(
            caret_width=11,
        )


def test_color_vision_assistance_requires_enum_value() -> None:
    with pytest.raises(
        TypeError,
        match="must be ColorVisionAssistance",
    ):
        AccessibilitySettings(
            color_vision_assistance="red-green",  # type: ignore[arg-type]
        )


def test_tool_window_override_normalizes_accent_color() -> None:
    override = ToolWindowAccessibilityOverride(
        tool_window_id="  git-changes  ",
        override_accent_color=True,
        accent_color="  #2f855a  ",
    )

    assert override.tool_window_id == "git-changes"
    assert override.accent_color == "#2F855A"


def test_tool_window_override_can_explicitly_reset_accent() -> None:
    override = ToolWindowAccessibilityOverride(
        tool_window_id="git-changes",
        override_accent_color=True,
        accent_color=None,
    )

    assert override.override_accent_color is True
    assert override.accent_color is None


def test_accent_color_requires_explicit_override_flag() -> None:
    with pytest.raises(
        ValueError,
        match="requires override_accent_color=True",
    ):
        ToolWindowAccessibilityOverride(
            tool_window_id="git-changes",
            accent_color="#2F855A",
        )


def test_document_area_override_cannot_enable_auto_hide() -> None:
    with pytest.raises(
        ValueError,
        match="cannot enable auto-hide",
    ):
        ToolWindowAccessibilityOverride(
            tool_window_id="git-changes",
            area=ToolWindowArea.DOCUMENT,
            pinned=False,
        )


def test_accessibility_profile_normalizes_override_tuple() -> None:
    override = ToolWindowAccessibilityOverride(
        tool_window_id="git-changes",
        pinned=True,
    )

    profile = AccessibilityProfile(
        name="Focus Coding",
        tool_window_overrides=[
            override,
        ],
    )

    assert isinstance(
        profile.profile_id,
        UUID,
    )
    assert profile.tool_window_overrides == (
        override,
    )


def test_accessibility_profile_rejects_duplicate_window_overrides() -> None:
    first = ToolWindowAccessibilityOverride(
        tool_window_id="git-changes",
        pinned=True,
    )
    second = ToolWindowAccessibilityOverride(
        tool_window_id="git-changes",
        visible=True,
    )

    with pytest.raises(
        ValueError,
        match="override IDs must be unique",
    ):
        AccessibilityProfile(
            name="Focus Coding",
            tool_window_overrides=(
                first,
                second,
            ),
        )


def test_accessibility_profile_normalizes_name() -> None:
    profile = AccessibilityProfile(
        name="  Focus Coding  ",
    )

    assert profile.name == "Focus Coding"