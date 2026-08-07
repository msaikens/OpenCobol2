"""Unit tests for the dockable tool-window manager."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
)

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


def test_service_activate_shows_the_real_dock_widget(
    qapp,
) -> None:
    # Editor §UIShell-1: `activate()`/`show()`/`hide()` used to only
    # mutate domain state -- the real `QDockWidget` never moved, so a
    # hidden panel (like Terminal, hidden by default) stayed invisible
    # forever with no way to bring it back through the View menu.
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
    assert beta.isVisible() is False

    service.activate(
        "beta",
    )

    assert beta.isVisible() is True


def test_service_hide_hides_the_real_dock_widget(
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
    assert alpha.isVisible() is True

    service.hide(
        "alpha",
    )

    assert alpha.isVisible() is False


def test_service_activate_raises_the_dock_widget_to_front(
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

    with patch.object(
        type(
            beta,
        ),
        "raise_",
    ) as mock_raise:
        service.activate(
            "beta",
        )

    mock_raise.assert_called_once()


def test_service_state_change_does_not_reenter_the_service(
    qapp,
) -> None:
    # The dock widget's own `visibilityChanged` signal fires when
    # `_on_state_changed` calls `setVisible()` -- `_on_visibility_changed`
    # must recognize the state already matches and not call back into
    # `show()`/`hide()` again, or every activation would recurse.
    service = _build_service()
    window = QMainWindow()
    window.show()
    manager = ToolWindowDockManager(
        main_window=window,
        tool_window_service=service,
    )
    call_count = 0
    original_store = service._store

    def counting_store(state):
        nonlocal call_count
        call_count += 1
        return original_store(
            state,
        )

    service._store = counting_store

    service.activate(
        "beta",
    )

    assert call_count == 1


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


def test_manager_uses_content_factory_when_provided(
    qapp,
) -> None:
    service = _build_service()
    window = QMainWindow()

    manager = ToolWindowDockManager(
        main_window=window,
        tool_window_service=service,
        content_factories={
            "alpha": lambda: QLabel(
                "Custom Alpha Content",
            ),
        },
    )

    alpha_content = manager.get_dock_widget(
        "alpha",
    ).widget()
    beta_content = manager.get_dock_widget(
        "beta",
    ).widget()

    assert isinstance(
        alpha_content,
        QLabel,
    )
    assert (
        alpha_content.text()
        == "Custom Alpha Content"
    )
    assert isinstance(
        beta_content,
        QLabel,
    )
    assert (
        beta_content.text()
        != "Custom Alpha Content"
    )
