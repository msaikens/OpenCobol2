"""IDE tool-window shell contracts and registries."""

from opencobol2.tool_windows.builtins import (
    BuiltInToolWindowIds,
    create_builtin_tool_window_registry,
)
from opencobol2.tool_windows.models import (
    ToolWindowAppearance,
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowGeometry,
    ToolWindowState,
    normalize_tool_window_accent_color,
)
from opencobol2.tool_windows.registry import (
    ToolWindowAlreadyRegisteredError,
    ToolWindowNotFoundError,
    ToolWindowRegistry,
)


__all__ = [
    "BuiltInToolWindowIds",
    "ToolWindowAlreadyRegisteredError",
    "ToolWindowAppearance",
    "ToolWindowArea",
    "ToolWindowDefinition",
    "ToolWindowGeometry",
    "ToolWindowNotFoundError",
    "ToolWindowRegistry",
    "ToolWindowState",
    "create_builtin_tool_window_registry",
    "normalize_tool_window_accent_color",
]