"""Domain models for dockable IDE tool windows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re


_HEX_COLOR_PATTERN = re.compile(
    r"^#[0-9A-Fa-f]{6}$",
)


class ToolWindowArea(StrEnum):
    """Supported IDE shell placement areas."""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    DOCUMENT = "document"


def normalize_tool_window_accent_color(
    value: str | None,
) -> str | None:
    """Normalize an optional RGB hexadecimal accent color."""

    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "Tool-window accent color must be a string."
        )

    normalized_value = value.strip()

    if not _HEX_COLOR_PATTERN.fullmatch(
        normalized_value,
    ):
        raise ValueError(
            "Tool-window accent color must use #RRGGBB format."
        )

    return normalized_value.upper()


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ToolWindowGeometry:
    """Persistable geometry for a floating tool window."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Validate tool-window geometry."""

        for name, value in (
            (
                "x",
                self.x,
            ),
            (
                "y",
                self.y,
            ),
            (
                "width",
                self.width,
            ),
            (
                "height",
                self.height,
            ),
        ):
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
                    f"Tool-window geometry {name} "
                    "must be an integer."
                )

        if self.width <= 0:
            raise ValueError(
                "Tool-window geometry width must be "
                "greater than zero."
            )

        if self.height <= 0:
            raise ValueError(
                "Tool-window geometry height must be "
                "greater than zero."
            )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ToolWindowDefinition:
    """Static definition of one IDE tool window."""

    tool_window_id: str
    title: str
    default_area: ToolWindowArea
    allowed_areas: tuple[ToolWindowArea, ...]
    default_visible: bool = False
    default_pinned: bool = True
    singleton: bool = True
    supports_accent_color: bool = True
    accessibility_name: str | None = None
    accessibility_description: str | None = None

    def __post_init__(self) -> None:
        """Normalize and validate a tool-window definition."""

        tool_window_id = _require_non_empty_string(
            self.tool_window_id,
            "Tool-window ID",
        )
        title = _require_non_empty_string(
            self.title,
            "Tool-window title",
        )

        if not isinstance(
            self.default_area,
            ToolWindowArea,
        ):
            raise TypeError(
                "Tool-window default area must be "
                "ToolWindowArea."
            )

        allowed_areas = tuple(
            self.allowed_areas,
        )

        if not allowed_areas:
            raise ValueError(
                "Tool-window allowed areas must not be empty."
            )

        if not all(
            isinstance(
                area,
                ToolWindowArea,
            )
            for area in allowed_areas
        ):
            raise TypeError(
                "Tool-window allowed areas must contain "
                "ToolWindowArea values."
            )

        if (
            len(
                set(
                    allowed_areas,
                )
            )
            != len(
                allowed_areas,
            )
        ):
            raise ValueError(
                "Tool-window allowed areas must be unique."
            )

        if self.default_area not in allowed_areas:
            raise ValueError(
                "Tool-window default area must be one of "
                "the allowed areas."
            )

        for name, value in (
            (
                "default visible",
                self.default_visible,
            ),
            (
                "default pinned",
                self.default_pinned,
            ),
            (
                "singleton",
                self.singleton,
            ),
            (
                "supports accent color",
                self.supports_accent_color,
            ),
        ):
            if not isinstance(
                value,
                bool,
            ):
                raise TypeError(
                    f"Tool-window {name} flag must be a boolean."
                )

        if (
            self.default_area
            is ToolWindowArea.DOCUMENT
            and not self.default_pinned
        ):
            raise ValueError(
                "Document-area tool windows must be pinned."
            )

        accessibility_name = (
            title
            if self.accessibility_name is None
            else _require_non_empty_string(
                self.accessibility_name,
                "Tool-window accessibility name",
            )
        )

        accessibility_description = (
            _normalize_optional_string(
                self.accessibility_description,
                "Tool-window accessibility description",
            )
        )

        object.__setattr__(
            self,
            "tool_window_id",
            tool_window_id,
        )
        object.__setattr__(
            self,
            "title",
            title,
        )
        object.__setattr__(
            self,
            "allowed_areas",
            allowed_areas,
        )
        object.__setattr__(
            self,
            "accessibility_name",
            accessibility_name,
        )
        object.__setattr__(
            self,
            "accessibility_description",
            accessibility_description,
        )


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ToolWindowAppearance:
    """User-customizable appearance for one tool window."""

    accent_color: str | None = None

    def __post_init__(self) -> None:
        """Normalize and validate tool-window appearance."""

        accent_color = normalize_tool_window_accent_color(
            self.accent_color,
        )

        object.__setattr__(
            self,
            "accent_color",
            accent_color,
        )

    @property
    def uses_default_accent(
        self,
    ) -> bool:
        """Return whether the application accent should be used."""

        return self.accent_color is None


@dataclass(
    frozen=True,
    slots=True,
    kw_only=True,
)
class ToolWindowState:
    """Current persistable shell state of one tool window."""

    tool_window_id: str
    area: ToolWindowArea
    visible: bool = False
    active: bool = False
    floating: bool = False
    pinned: bool = True
    appearance: ToolWindowAppearance = field(
        default_factory=ToolWindowAppearance,
    )
    geometry: ToolWindowGeometry | None = None
    tab_group_id: str | None = None

    def __post_init__(self) -> None:
        """Normalize and validate tool-window shell state."""

        tool_window_id = _require_non_empty_string(
            self.tool_window_id,
            "Tool-window state ID",
        )

        if not isinstance(
            self.area,
            ToolWindowArea,
        ):
            raise TypeError(
                "Tool-window state area must be ToolWindowArea."
            )

        for name, value in (
            (
                "visible",
                self.visible,
            ),
            (
                "active",
                self.active,
            ),
            (
                "floating",
                self.floating,
            ),
            (
                "pinned",
                self.pinned,
            ),
        ):
            if not isinstance(
                value,
                bool,
            ):
                raise TypeError(
                    f"Tool-window state {name} must be a boolean."
                )

        if not isinstance(
            self.appearance,
            ToolWindowAppearance,
        ):
            raise TypeError(
                "Tool-window state appearance must be "
                "ToolWindowAppearance."
            )

        if (
            self.geometry is not None
            and not isinstance(
                self.geometry,
                ToolWindowGeometry,
            )
        ):
            raise TypeError(
                "Tool-window state geometry must be "
                "ToolWindowGeometry."
            )

        if self.active and not self.visible:
            raise ValueError(
                "An active tool window must be visible."
            )

        if self.floating and not self.pinned:
            raise ValueError(
                "A floating tool window must be pinned."
            )

        if (
            self.area is ToolWindowArea.DOCUMENT
            and not self.pinned
        ):
            raise ValueError(
                "A document-area tool window must be pinned."
            )

        tab_group_id = _normalize_optional_string(
            self.tab_group_id,
            "Tool-window tab group ID",
        )

        object.__setattr__(
            self,
            "tool_window_id",
            tool_window_id,
        )
        object.__setattr__(
            self,
            "tab_group_id",
            tab_group_id,
        )

    @property
    def auto_hide(
        self,
    ) -> bool:
        """Return whether a docked tool window uses auto-hide."""

        return (
            not self.floating
            and self.area is not ToolWindowArea.DOCUMENT
            and not self.pinned
        )


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


def _normalize_optional_string(
    value: str | None,
    name: str,
) -> str | None:
    """Normalize an optional non-empty string."""

    if value is None:
        return None

    return _require_non_empty_string(
        value,
        name,
    )