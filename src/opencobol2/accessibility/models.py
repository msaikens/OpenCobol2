"""Domain models for OpenCobol2 accessibility preferences."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4

from opencobol2.tool_windows import (
    ToolWindowArea,
    normalize_tool_window_accent_color,
)


class ColorVisionAssistance(StrEnum):
    """Supported color-vision assistance strategies."""

    OFF = "off"
    RED_GREEN = "red-green"
    BLUE_YELLOW = "blue-yellow"
    MONOCHROME_SAFE = "monochrome-safe"


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class AccessibilitySettings:
    """User preferences that affect IDE accessibility."""

    interface_scale: float = 1.0
    editor_scale: float = 1.0
    high_contrast: bool = False
    reduce_motion: bool = False
    reduce_visual_effects: bool = False
    increase_focus_indicators: bool = False
    always_show_mnemonics: bool = False
    screen_reader_optimizations: bool = False
    color_vision_assistance: ColorVisionAssistance = (
        ColorVisionAssistance.OFF
    )
    caret_width: int = 1
    minimum_control_size: int = 0

    def __post_init__(self) -> None:
        """Normalize and validate accessibility preferences."""

        interface_scale = _normalize_scale(
            self.interface_scale,
            "Interface scale",
        )
        editor_scale = _normalize_scale(
            self.editor_scale,
            "Editor scale",
        )

        for name, value in (
            (
                "high contrast",
                self.high_contrast,
            ),
            (
                "reduce motion",
                self.reduce_motion,
            ),
            (
                "reduce visual effects",
                self.reduce_visual_effects,
            ),
            (
                "increase focus indicators",
                self.increase_focus_indicators,
            ),
            (
                "always show mnemonics",
                self.always_show_mnemonics,
            ),
            (
                "screen reader optimizations",
                self.screen_reader_optimizations,
            ),
        ):
            if not isinstance(
                value,
                bool,
            ):
                raise TypeError(
                    f"Accessibility {name} must be a boolean."
                )

        if not isinstance(
            self.color_vision_assistance,
            ColorVisionAssistance,
        ):
            raise TypeError(
                "Color-vision assistance must be "
                "ColorVisionAssistance."
            )

        caret_width = _require_integer(
            self.caret_width,
            "Accessibility caret width",
        )

        if not 1 <= caret_width <= 10:
            raise ValueError(
                "Accessibility caret width must be "
                "between 1 and 10."
            )

        minimum_control_size = _require_integer(
            self.minimum_control_size,
            "Accessibility minimum control size",
        )

        if not 0 <= minimum_control_size <= 128:
            raise ValueError(
                "Accessibility minimum control size must be "
                "between 0 and 128."
            )

        object.__setattr__(
            self,
            "interface_scale",
            interface_scale,
        )
        object.__setattr__(
            self,
            "editor_scale",
            editor_scale,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ToolWindowAccessibilityOverride:
    """Selective tool-window override stored in an accessibility profile."""

    tool_window_id: str
    area: ToolWindowArea | None = None
    visible: bool | None = None
    pinned: bool | None = None
    override_accent_color: bool = False
    accent_color: str | None = None

    def __post_init__(self) -> None:
        """Normalize and validate a tool-window profile override."""

        tool_window_id = _require_non_empty_string(
            self.tool_window_id,
            "Tool-window override ID",
        )

        if (
            self.area is not None
            and not isinstance(
                self.area,
                ToolWindowArea,
            )
        ):
            raise TypeError(
                "Tool-window override area must be "
                "ToolWindowArea."
            )

        for name, value in (
            (
                "visible",
                self.visible,
            ),
            (
                "pinned",
                self.pinned,
            ),
        ):
            if (
                value is not None
                and not isinstance(
                    value,
                    bool,
                )
            ):
                raise TypeError(
                    f"Tool-window override {name} must be "
                    "a boolean."
                )

        if not isinstance(
            self.override_accent_color,
            bool,
        ):
            raise TypeError(
                "Tool-window accent override flag must be "
                "a boolean."
            )

        if (
            not self.override_accent_color
            and self.accent_color is not None
        ):
            raise ValueError(
                "Tool-window accent color requires "
                "override_accent_color=True."
            )

        accent_color = (
            normalize_tool_window_accent_color(
                self.accent_color,
            )
            if self.override_accent_color
            else None
        )

        if (
            self.area is ToolWindowArea.DOCUMENT
            and self.pinned is False
        ):
            raise ValueError(
                "A document-area tool-window override "
                "cannot enable auto-hide."
            )

        object.__setattr__(
            self,
            "tool_window_id",
            tool_window_id,
        )
        object.__setattr__(
            self,
            "accent_color",
            accent_color,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class AccessibilityProfile:
    """Named accessibility and working-environment profile."""

    name: str
    profile_id: UUID = field(
        default_factory=uuid4,
    )
    settings: AccessibilitySettings = field(
        default_factory=AccessibilitySettings,
    )
    tool_window_overrides: tuple[
        ToolWindowAccessibilityOverride,
        ...,
    ] = ()

    def __post_init__(self) -> None:
        """Normalize and validate an accessibility profile."""

        if not isinstance(
            self.profile_id,
            UUID,
        ):
            raise TypeError(
                "Accessibility profile ID must be a UUID."
            )

        name = _require_non_empty_string(
            self.name,
            "Accessibility profile name",
        )

        if not isinstance(
            self.settings,
            AccessibilitySettings,
        ):
            raise TypeError(
                "Accessibility profile settings must be "
                "AccessibilitySettings."
            )

        tool_window_overrides = tuple(
            self.tool_window_overrides,
        )

        if not all(
            isinstance(
                override,
                ToolWindowAccessibilityOverride,
            )
            for override in tool_window_overrides
        ):
            raise TypeError(
                "Accessibility profile tool-window overrides "
                "must contain ToolWindowAccessibilityOverride "
                "instances."
            )

        tool_window_ids = tuple(
            override.tool_window_id
            for override in tool_window_overrides
        )

        if (
            len(
                set(
                    tool_window_ids,
                )
            )
            != len(
                tool_window_ids,
            )
        ):
            raise ValueError(
                "Accessibility profile tool-window override IDs "
                "must be unique."
            )

        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "tool_window_overrides",
            tool_window_overrides,
        )


def _normalize_scale(
    value: float,
    name: str,
) -> float:
    """Normalize and validate an accessibility scale."""

    if (
        not isinstance(
            value,
            (
                int,
                float,
            ),
        )
        or isinstance(
            value,
            bool,
        )
    ):
        raise TypeError(
            f"{name} must be a number."
        )

    normalized_value = float(
        value,
    )

    if not 0.5 <= normalized_value <= 4.0:
        raise ValueError(
            f"{name} must be between 0.5 and 4.0."
        )

    return normalized_value


def _require_integer(
    value: int,
    name: str,
) -> int:
    """Require a non-boolean integer."""

    if (
        not isinstance(
            value,
            int,
        )
        or isinstance(
            value,
            bool,
        )
    ):
        raise TypeError(
            f"{name} must be an integer."
        )

    return value


def _require_non_empty_string(
    value: str,
    name: str,
) -> str:
    """Require and normalize a non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"{name} must not be empty."
        )

    return normalized_value