"""Renders registered tool windows as live dockable Qt panels.

Docking placement and visibility are wired to the real ToolWindowService.
Pinning/auto-hide and floating-geometry restoration are not implemented yet;
QDockWidget's native floating/closable behavior is used as-is.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QWidget,
)

from opencobol2.services.tool_windows import ToolWindowService
from opencobol2.tool_windows import (
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowState,
)


type ToolWindowContentFactory = Callable[[], QWidget]


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

    :param area: The domain-level tool-window area to translate.
    :returns: The Qt dock widget area that `area` maps to, or
        :attr:`Qt.DockWidgetArea.RightDockWidgetArea` when `area` has no
        entry in the mapping (currently only
        :attr:`ToolWindowArea.DOCUMENT`).
    """

    return _AREA_TO_QT_DOCK_AREA.get(
        area,
        Qt.DockWidgetArea.RightDockWidgetArea,
    )


class ToolWindowDockManager:
    """Creates and synchronizes dock widgets for registered tool windows.

    :ivar _main_window: The Qt main window that owns every dock widget
        this manager creates.
    :ivar _tool_window_service: The domain-level service that tracks
        each tool window's area, visibility, and active state, and that
        this manager keeps synchronized with the real dock widgets.
    :ivar _content_factories: Callables, keyed by tool-window ID, that
        build the real content widget for a tool window. Tool windows
        with no entry here get placeholder content instead.
    :ivar _dock_widgets: Every created :class:`QDockWidget`, keyed by
        tool-window ID.
    """

    def __init__(
        self,
        *,
        main_window: QMainWindow,
        tool_window_service: ToolWindowService,
        content_factories: Mapping[
            str,
            ToolWindowContentFactory,
        ]
        | None = None,
    ) -> None:
        """Build one dock widget per registered tool-window definition.

        Tool windows without an entry in `content_factories` fall back to
        placeholder content — most panels don't have a real widget yet.

        Also subscribes to the tool-window service's state-change
        notifications (see :meth:`_on_state_changed`). Without that
        subscription, every View-menu tool-window command
        (`activate()`) and the two hand-rolled reveal-panel workarounds
        elsewhere would only ever update domain state -- the real
        `QDockWidget` would never move, so a hidden panel would stay
        hidden forever with no way to bring it back through the menu.

        :param main_window: The Qt main window to dock every tool
            window's widget into.
        :param tool_window_service: The domain-level service that owns
            each tool window's registered definitions and current
            state.
        :param content_factories: Optional callables, keyed by
            tool-window ID, that build the real content widget for a
            tool window. Tool windows with no entry here get
            placeholder content instead.
        :raises TypeError: If `main_window` is not a
            :class:`QMainWindow`, or `tool_window_service` is not a
            :class:`ToolWindowService`.
        """

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
        self._content_factories = (
            {}
            if content_factories is None
            else dict(
                content_factories,
            )
        )
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

        tool_window_service.add_listener(
            self._on_state_changed,
        )

    @property
    def dock_widgets(
        self,
    ) -> dict[str, QDockWidget]:
        """Return created dock widgets keyed by tool-window ID.

        :returns: A shallow copy of the internal tool-window-ID-to-dock-
            widget mapping, safe for the caller to hold onto or mutate.
        """

        return dict(
            self._dock_widgets,
        )

    def get_dock_widget(
        self,
        tool_window_id: str,
    ) -> QDockWidget:
        """Return the dock widget for one registered tool window.

        :param tool_window_id: The ID of the registered tool window
            whose dock widget should be returned.
        :returns: The :class:`QDockWidget` created for `tool_window_id`.
        :raises KeyError: If `tool_window_id` has no created dock
            widget.
        """

        return self._dock_widgets[
            tool_window_id
        ]

    def _create_dock_widget(
        self,
        definition: ToolWindowDefinition,
    ) -> QDockWidget:
        """Create, place, and wire one tool window's dock widget.

        :param definition: The registered tool-window definition to
            build a dock widget for.
        :returns: The newly created and docked :class:`QDockWidget`,
            already registered in :attr:`_dock_widgets`.
        """

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

        content_factory = self._content_factories.get(
            definition.tool_window_id,
        )
        dock_widget.setWidget(
            content_factory()
            if content_factory is not None
            else _create_placeholder_content(
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

    def _on_state_changed(
        self,
        state: ToolWindowState,
    ) -> None:
        """Reflect a tool window's domain-state change onto its real dock widget.

        The reverse direction (:meth:`_on_visibility_changed`) already
        guards against exactly the re-entrant loop this could otherwise
        cause: it only calls back into the service when the dock
        widget's new visibility actually differs from the state that
        was just stored, and by the time this listener runs, the store
        already happened.

        :param state: The tool window's new state, as reported by the
            tool-window service.
        :returns: None. If a dock widget exists for `state`'s
            tool-window ID, its visibility is set to match `state`, and
            it is raised when the state marks it both visible and
            active. Silently does nothing if no dock widget is
            registered for that ID.
        """

        dock_widget = self._dock_widgets.get(
            state.tool_window_id,
        )

        if dock_widget is None:
            return

        dock_widget.setVisible(
            state.visible,
        )

        if state.visible and state.active:
            dock_widget.raise_()

    def _on_visibility_changed(
        self,
        tool_window_id: str,
        visible: bool,
    ) -> None:
        """Reflect a dock widget's visibility change back into the service.

        :param tool_window_id: The ID of the tool window whose dock
            widget changed visibility.
        :param visible: The dock widget's new visibility.
        :returns: None. Calls into the tool-window service to show or
            hide `tool_window_id` when `visible` differs from the
            service's currently stored visibility; does nothing when it
            already matches, which avoids feeding the change back into
            :meth:`_on_state_changed` as a redundant update.
        """

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
    """Create placeholder content for a tool window with no real widget yet.

    :param definition: The tool-window definition to build placeholder
        content for.
    :returns: A word-wrapped, top-left-aligned :class:`QLabel` showing
        the definition's accessibility description, or its title if no
        description is set.
    """

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
