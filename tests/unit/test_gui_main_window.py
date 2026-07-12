"""Unit tests for the OpenCobol2 MainWindow shell."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QPalette

from opencobol2.commands import (
    Command,
    CommandContribution,
    CommandContributionRegistry,
    CommandRegistry,
    CommandSurfaceKind,
)
from opencobol2.gui.main_window import MainWindow
from opencobol2.services.command_contributions import (
    CommandContributionService,
)
from opencobol2.services.commands import CommandService
from opencobol2.services.status_bar import StatusBarService
from opencobol2.services.theming import ThemeService
from opencobol2.services.tool_windows import ToolWindowService
from opencobol2.status_bar import (
    StatusBarItemAlignment,
    StatusBarItemContent,
    StatusBarItemDefinition,
    StatusBarItemRegistry,
)
from opencobol2.theming import (
    create_builtin_theme_registry,
    DARK_THEME_ID,
    LIGHT_THEME_ID,
)
from opencobol2.tool_windows import (
    ToolWindowArea,
    ToolWindowDefinition,
    ToolWindowRegistry,
)


def _build_services() -> tuple[
    CommandContributionService,
    ToolWindowService,
    ThemeService,
]:
    command_registry = CommandRegistry()
    command_registry.register(
        Command(
            command_id="test.new",
            title="New",
            handler=lambda context: "new",
        )
    )

    contribution_registry = CommandContributionRegistry()
    contribution_registry.register(
        CommandContribution(
            contribution_id="menu.file.new",
            command_id="test.new",
            surface_kind=CommandSurfaceKind.MENU,
            surface_id="file",
        )
    )
    contribution_registry.register(
        CommandContribution(
            contribution_id="toolbar.main.new",
            command_id="test.new",
            surface_kind=CommandSurfaceKind.TOOLBAR,
            surface_id="main",
        )
    )

    contribution_service = CommandContributionService(
        command_service=CommandService(
            registry=command_registry,
        ),
        contribution_registry=contribution_registry,
    )

    tool_window_registry = ToolWindowRegistry()
    tool_window_registry.register(
        ToolWindowDefinition(
            tool_window_id="alpha",
            title="Alpha",
            default_area=ToolWindowArea.LEFT,
            allowed_areas=(
                ToolWindowArea.LEFT,
            ),
            default_visible=True,
        )
    )
    tool_window_service = ToolWindowService(
        registry=tool_window_registry,
    )

    theme_service = ThemeService(
        registry=create_builtin_theme_registry(),
        initial_theme_id=DARK_THEME_ID,
    )

    return (
        contribution_service,
        tool_window_service,
        theme_service,
    )


def test_main_window_builds_menus_toolbars_and_docks(
    qapp,
) -> None:
    (
        contribution_service,
        tool_window_service,
        theme_service,
    ) = _build_services()

    window = MainWindow(
        contribution_service=contribution_service,
        tool_window_service=tool_window_service,
        theme_service=theme_service,
        top_level_menus=(
            (
                "file",
                "&File",
            ),
        ),
        toolbar_surface_ids=(
            "main",
        ),
    )

    assert set(
        window.menus.keys(),
    ) == {"file"}
    assert set(
        window.toolbars.keys(),
    ) == {"main"}
    assert set(
        window.dock_manager.dock_widgets.keys(),
    ) == {"alpha"}
    assert (
        window.windowTitle()
        == "OpenCobol2"
    )


def test_main_window_applies_active_theme(
    qapp,
) -> None:
    (
        contribution_service,
        tool_window_service,
        theme_service,
    ) = _build_services()

    window = MainWindow(
        contribution_service=contribution_service,
        tool_window_service=tool_window_service,
        theme_service=theme_service,
        top_level_menus=(),
    )

    assert (
        window.palette().color(
            QPalette.ColorRole.Window,
        ).name().upper()
        == "#1E1E1E"
    )

    theme_service.set_active_theme(
        LIGHT_THEME_ID,
    )
    window.apply_active_theme()

    assert (
        window.palette().color(
            QPalette.ColorRole.Window,
        ).name().upper()
        == "#FFFFFF"
    )


def test_main_window_rejects_invalid_contribution_service(
    qapp,
) -> None:
    (
        _,
        tool_window_service,
        theme_service,
    ) = _build_services()

    with pytest.raises(
        TypeError,
        match=(
            "Main window contribution service must be "
            "CommandContributionService"
        ),
    ):
        MainWindow(
            contribution_service=object(),  # type: ignore[arg-type]
            tool_window_service=tool_window_service,
            theme_service=theme_service,
            top_level_menus=(),
        )


def test_main_window_rejects_invalid_tool_window_service(
    qapp,
) -> None:
    (
        contribution_service,
        _,
        theme_service,
    ) = _build_services()

    with pytest.raises(
        TypeError,
        match=(
            "Main window tool-window service must be "
            "ToolWindowService"
        ),
    ):
        MainWindow(
            contribution_service=contribution_service,
            tool_window_service=object(),  # type: ignore[arg-type]
            theme_service=theme_service,
            top_level_menus=(),
        )


def test_main_window_rejects_invalid_theme_service(
    qapp,
) -> None:
    (
        contribution_service,
        tool_window_service,
        _,
    ) = _build_services()

    with pytest.raises(
        TypeError,
        match=(
            "Main window theme service must be ThemeService"
        ),
    ):
        MainWindow(
            contribution_service=contribution_service,
            tool_window_service=tool_window_service,
            theme_service=object(),  # type: ignore[arg-type]
            top_level_menus=(),
        )


def test_main_window_without_status_bar_service_has_no_labels(
    qapp,
) -> None:
    (
        contribution_service,
        tool_window_service,
        theme_service,
    ) = _build_services()

    window = MainWindow(
        contribution_service=contribution_service,
        tool_window_service=tool_window_service,
        theme_service=theme_service,
        top_level_menus=(),
    )

    assert window._status_bar_labels == {}
    # Must be a safe no-op without a configured status bar service.
    window.refresh_status_bar()


def test_main_window_builds_status_bar_from_service(
    qapp,
) -> None:
    (
        contribution_service,
        tool_window_service,
        theme_service,
    ) = _build_services()

    status_bar_registry = StatusBarItemRegistry()
    status_bar_registry.register(
        StatusBarItemDefinition(
            item_id="message",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text="Ready",
            ),
        )
    )
    status_bar_service = StatusBarService(
        registry=status_bar_registry,
    )

    window = MainWindow(
        contribution_service=contribution_service,
        tool_window_service=tool_window_service,
        theme_service=theme_service,
        top_level_menus=(),
        status_bar_service=status_bar_service,
    )

    assert (
        window._status_bar_labels[
            "message"
        ].text()
        == "Ready"
    )


def test_apply_active_theme_refreshes_status_bar(
    qapp,
) -> None:
    (
        contribution_service,
        tool_window_service,
        theme_service,
    ) = _build_services()

    text_holder = ["First"]
    status_bar_registry = StatusBarItemRegistry()
    status_bar_registry.register(
        StatusBarItemDefinition(
            item_id="message",
            alignment=StatusBarItemAlignment.LEFT,
            provider=lambda: StatusBarItemContent(
                text=text_holder[0],
            ),
        )
    )
    status_bar_service = StatusBarService(
        registry=status_bar_registry,
    )

    window = MainWindow(
        contribution_service=contribution_service,
        tool_window_service=tool_window_service,
        theme_service=theme_service,
        top_level_menus=(),
        status_bar_service=status_bar_service,
    )

    text_holder[0] = "Second"
    window.apply_active_theme()

    assert (
        window._status_bar_labels[
            "message"
        ].text()
        == "Second"
    )


def test_main_window_rejects_invalid_status_bar_service(
    qapp,
) -> None:
    (
        contribution_service,
        tool_window_service,
        theme_service,
    ) = _build_services()

    with pytest.raises(
        TypeError,
        match=(
            "Main window status bar service must be "
            "StatusBarService or None"
        ),
    ):
        MainWindow(
            contribution_service=contribution_service,
            tool_window_service=tool_window_service,
            theme_service=theme_service,
            top_level_menus=(),
            status_bar_service=object(),  # type: ignore[arg-type]
        )
