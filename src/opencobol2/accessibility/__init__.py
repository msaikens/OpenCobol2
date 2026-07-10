"""Accessibility preferences and profile contracts."""

from opencobol2.accessibility.models import (
    AccessibilityProfile,
    AccessibilitySettings,
    ColorVisionAssistance,
    ToolWindowAccessibilityOverride,
)
from opencobol2.accessibility.registry import (
    AccessibilityProfileAlreadyRegisteredError,
    AccessibilityProfileNotFoundError,
    AccessibilityProfileRegistry,
)


__all__ = [
    "AccessibilityProfile",
    "AccessibilityProfileAlreadyRegisteredError",
    "AccessibilityProfileNotFoundError",
    "AccessibilityProfileRegistry",
    "AccessibilitySettings",
    "ColorVisionAssistance",
    "ToolWindowAccessibilityOverride",
]