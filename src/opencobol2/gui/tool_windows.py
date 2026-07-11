"""Renders registered tool windows as live dockable Qt panels.

Docking placement and visibility are wired to the real ToolWindowService.
Pinning/auto-hide and floating-geometry restoration are not implemented yet;
QDockWidget's native floating/closable behavior is used as-is.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
)

from opencobol2.services.tool_windows import ToolWindowService
from opencobol2.tool_windows import (
    ToolWindowArea,
    ToolWindowDefinition,
)


_AREA_TO_QT_DOCK_AREA = {
    ToolWindowArea.LEFT: Qt.DockWidgetArea.LeftDockWidgetArea,
    ToolWindowArea.RIGHT: Qt.DockWidgetArea.RightDockWidgetArea,
    ToolWindowArea.TOP: Qt.DockWidgetArea.TopDockWidgetArea,
    ToolWindowArea.BOTTOM: Qt.DockWidgetArea.BottomDockWidgetArea,
}


def dock_area_for(
    area: ToolWindowArea,
) -> Qt.DockWidgetArea:
    """Map a tool-window area to a Qt dock widget area.

    The DOCUMENT area has no rendered editor tab region yet, so it falls
    back to the right dock area until Phase 3's editor shell exists.
    """

    return _AREA_TO_QT_DOCK_AREA.get(
        area,
        Qt.DockWidgetArea.RightDockWidgetArea,
    )


class ToolWindowDockManager:
    """Creates and synchronizes dock widgets for registered tool windows."""

    def __init__(
        self,
        *,
        main_window: QMainWindow,
        tool_window_service: ToolWindowService,
    ) -> None:
        """Build one dock widget per registered tool-window definition."""

        if not isinstance(
            main_window,
            QMainWindow,
        ):
            raise TypeError(
                "Dock manager main window must be QMainWindow."
            )

        if not isinstance(
            tool_window_service,
            ToolWindowService,
        ):
            raise TypeError(
                "Dock manager tool-window service must be "
                "ToolWindowService."
            )

        self._main_window = main_window
        self._tool_window_service = tool_window_service
        self._dock_widgets: dict[
            str,
            QDockWidget,
        ] = {}

        for definition in (
            tool_window_service.registry.definitions
        ):
            self._create_dock_widget(
                definition,
            )

    @property
    def dock_widgets(
        self,
    ) -> dict[str, QDockWidget]:
        """Return created dock widgets keyed by tool-window ID."""

        return dict(
            self._dock_widgets,
        )

    def get_dock_widget(
        self,
        tool_window_id: str,
    ) -> QDockWidget:
        """Return the dock widget for one registered tool window."""

        return self._dock_widgets[
            tool_window_id
        ]

    def _create_dock_widget(
        self,
        definition: ToolWindowDefinition,
    ) -> QDockWidget:
        """Create, place, and wire one tool window's dock widget."""

        state = self._tool_window_service.get_state(
            definition.tool_window_id,
        )

        dock_widget = QDockWidget(
            definition.title,
            self._main_window,
        )
        dock_widget.setObjectName(
            definition.tool_window_id,
        )
        dock_widget.setAccessibleName(
            definition.accessibility_name
            or definition.title,
        )

        if definition.accessibility_description:
            dock_widget.setAccessibleDescription(
                definition.accessibility_description,
            )

        dock_widget.setWidget(
            _create_placeholder_content(
                definition,
            )
        )

        self._main_window.addDockWidget(
            dock_area_for(
                state.area,
            ),
            dock_widget,
        )
        dock_widget.setVisible(
            state.visible,
        )

        dock_widget.visibilityChanged.connect(
            lambda visible,
            tool_window_id=definition.tool_window_id: (
                self._on_visibility_changed(
                    tool_window_id,
                    visible,
                )
            )
        )

        self._dock_widgets[
            definition.tool_window_id
        ] = dock_widget

        return dock_widget

    def _on_visibility_changed(
        self,
        tool_window_id: str,
        visible: bool,
    ) -> None:
        """Reflect a dock widget's visibility change back into the service."""

        current_state = (
            self._tool_window_service.get_state(
                tool_window_id,
            )
        )

        if visible == current_state.visible:
            return

        if visible:
            self._tool_window_service.show(
                tool_window_id,
            )
        else:
            self._tool_window_service.hide(
                tool_window_id,
            )


def _create_placeholder_content(
    definition: ToolWindowDefinition,
) -> QLabel:
    """Create placeholder content for a tool window with no real widget yet."""

    label = QLabel(
        definition.accessibility_description
        or definition.title,
    )
    label.setWordWrap(
        True,
    )
    label.setAlignment(
        Qt.AlignmentFlag.AlignTop
        | Qt.AlignmentFlag.AlignLeft,
    )
    label.setMargin(
        8,
    )

    return label
