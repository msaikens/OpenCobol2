"""The OpenCobol2 main application window shell."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QStatusBar,
    QToolBar,
    QWidget,
)

from opencobol2.gui.command_menus import build_menu_bar
from opencobol2.gui.theming import apply_theme_to_widget
from opencobol2.gui.tool_windows import ToolWindowDockManager
from opencobol2.gui.toolbars import build_toolbar
from opencobol2.services.command_contributions import (
    CommandContributionService,
)
from opencobol2.services.theming import ThemeService
from opencobol2.services.tool_windows import ToolWindowService


class MainWindow(QMainWindow):
    """The OpenCobol2 IDE shell: menu bar, toolbars, and docked tool windows."""

    def __init__(
        self,
        *,
        contribution_service: CommandContributionService,
        tool_window_service: ToolWindowService,
        theme_service: ThemeService,
        top_level_menus: Sequence[tuple[str, str]],
        toolbar_surface_ids: Sequence[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        """Build the OpenCobol2 shell from the supplied application services."""

        super().__init__(
            parent,
        )

        if not isinstance(
            contribution_service,
            CommandContributionService,
        ):
            raise TypeError(
                "Main window contribution service must be "
                "CommandContributionService."
            )

        if not isinstance(
            tool_window_service,
            ToolWindowService,
        ):
            raise TypeError(
                "Main window tool-window service must be "
                "ToolWindowService."
            )

        if not isinstance(
            theme_service,
            ThemeService,
        ):
            raise TypeError(
                "Main window theme service must be ThemeService."
            )

        self._contribution_service = contribution_service
        self._tool_window_service = tool_window_service
        self._theme_service = theme_service

        self.setWindowTitle(
            "OpenCobol2",
        )
        self.setObjectName(
            "OpenCobol2MainWindow",
        )

        self._menus = build_menu_bar(
            self.menuBar(),
            top_level_menus,
            contribution_service,
        )

        self._toolbars: dict[
            str,
            QToolBar,
        ] = {}

        for surface_id in toolbar_surface_ids:
            toolbar = QToolBar(
                surface_id,
                self,
            )
            toolbar.setObjectName(
                surface_id,
            )
            build_toolbar(
                toolbar,
                surface_id,
                contribution_service,
            )
            self.addToolBar(
                toolbar,
            )
            self._toolbars[surface_id] = toolbar

        self.setStatusBar(
            QStatusBar(
                self,
            )
        )

        self._dock_manager = ToolWindowDockManager(
            main_window=self,
            tool_window_service=tool_window_service,
        )

        self.apply_active_theme()

    @property
    def menus(
        self,
    ) -> dict[str, QMenu]:
        """Return the shell's top-level menus keyed by surface ID."""

        return dict(
            self._menus,
        )

    @property
    def toolbars(
        self,
    ) -> dict[str, QToolBar]:
        """Return the shell's toolbars keyed by surface ID."""

        return dict(
            self._toolbars,
        )

    @property
    def dock_manager(
        self,
    ) -> ToolWindowDockManager:
        """Return the tool-window dock manager."""

        return self._dock_manager

    def apply_active_theme(
        self,
    ) -> None:
        """Re-apply the current active theme's palette to the shell."""

        apply_theme_to_widget(
            self,
            self._theme_service.active_theme,
        )
