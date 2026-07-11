"""Unit tests for the dockable tool-window manager."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow

from opencobol2.gui.tool_windows import (
    dock_area_for,
    ToolWindowDockManager,
)
from opencobol2.services.tool_windows import ToolWindowService
from opencobol2.tool_windows import (
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowRegistry,
)


def _build_service() -> ToolWindowService:
    registry = ToolWindowRegistry()
    registry.register(
        ToolWindowDefinition(
            tool_window_id="alpha",
            title="Alpha",
            default_area=ToolWindowArea.LEFT,
            allowed_areas=(
                ToolWindowArea.LEFT,
                ToolWindowArea.RIGHT,
            ),
            default_visible=True,
            accessibility_description="Alpha panel.",
        )
    )
    registry.register(
        ToolWindowDefinition(
            tool_window_id="beta",
            title="Beta",
            default_area=ToolWindowArea.BOTTOM,
            allowed_areas=(
                ToolWindowArea.BOTTOM,
            ),
            default_visible=False,
        )
    )

    return ToolWindowService(
        registry=registry,
    )


def test_dock_area_mapping() -> None:
    assert (
        dock_area_for(
            ToolWindowArea.LEFT,
        )
        == Qt.DockWidgetArea.LeftDockWidgetArea
    )
    assert (
        dock_area_for(
            ToolWindowArea.RIGHT,
        )
        == Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert (
        dock_area_for(
            ToolWindowArea.TOP,
        )
        == Qt.DockWidgetArea.TopDockWidgetArea
    )
    assert (
        dock_area_for(
            ToolWindowArea.BOTTOM,
        )
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert (
        dock_area_for(
            ToolWindowArea.DOCUMENT,
        )
        == Qt.DockWidgetArea.RightDockWidgetArea
    )


def test_manager_creates_one_dock_widget_per_definition(
    qapp,
) -> None:
    service = _build_service()
    window = QMainWindow()

    manager = ToolWindowDockManager(
        main_window=window,
        tool_window_service=service,
    )

    assert set(
        manager.dock_widgets.keys(),
    ) == {
        "alpha",
        "beta",
    }


def test_manager_applies_initial_visibility_and_area(
    qapp,
) -> None:
    service = _build_service()
    window = QMainWindow()
    window.show()
    manager = ToolWindowDockManager(
        main_window=window,
        tool_window_service=service,
    )

    alpha = manager.get_dock_widget(
        "alpha",
    )
    beta = manager.get_dock_widget(
        "beta",
    )

    assert alpha.isVisible() is True
    assert beta.isVisible() is False
    assert (
        window.dockWidgetArea(
            alpha,
        )
        == Qt.DockWidgetArea.LeftDockWidgetArea
    )
    assert (
        window.dockWidgetArea(
            beta,
        )
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )


def test_manager_sets_accessible_description(
    qapp,
) -> None:
    service = _build_service()
    window = QMainWindow()
    manager = ToolWindowDockManager(
        main_window=window,
        tool_window_service=service,
    )

    alpha = manager.get_dock_widget(
        "alpha",
    )

    assert (
        alpha.accessibleDescription()
        == "Alpha panel."
    )


def test_dock_widget_visibility_syncs_back_to_service(
    qapp,
) -> None:
    service = _build_service()
    window = QMainWindow()
    window.show()
    manager = ToolWindowDockManager(
        main_window=window,
        tool_window_service=service,
    )

    beta = manager.get_dock_widget(
        "beta",
    )
    beta.setVisible(
        True,
    )

    assert (
        service.get_state(
            "beta",
        ).visible
        is True
    )

    beta.setVisible(
        False,
    )

    assert (
        service.get_state(
            "beta",
        ).visible
        is False
    )


def test_manager_rejects_non_main_window(
    qapp,
) -> None:
    service = _build_service()

    with pytest.raises(
        TypeError,
        match=(
            "Dock manager main window must be QMainWindow"
        ),
    ):
        ToolWindowDockManager(
            main_window=object(),  # type: ignore[arg-type]
            tool_window_service=service,
        )


def test_manager_rejects_non_tool_window_service(
    qapp,
) -> None:
    window = QMainWindow()

    with pytest.raises(
        TypeError,
        match=(
            "Dock manager tool-window service must be "
            "ToolWindowService"
        ),
    ):
        ToolWindowDockManager(
            main_window=window,
            tool_window_service=object(),  # type: ignore[arg-type]
        )
