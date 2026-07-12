"""Unit tests for the OpenCobol2 application bootstrap."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPalette

from opencobol2.gui.application import (
    create_main_window,
    TOP_LEVEL_MENUS,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import create_project
from opencobol2.settings import (
    SettingsService,
    SettingsStorage,
    ThemeSettings,
)


def _project_explorer_content(
    window,
) -> ProjectExplorerWidget:
    return (
        window.dock_manager.get_dock_widget(
            "project-explorer",
        ).widget()
    )


def test_create_main_window_wires_builtin_registries(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )

    window = create_main_window(
        settings_service=settings_service,
    )

    assert set(
        window.menus.keys(),
    ) == {
        surface_id
        for surface_id, _ in TOP_LEVEL_MENUS
    }
    assert (
        len(
            window.dock_manager.dock_widgets,
        )
        == 6
    )
    assert (
        window.windowTitle()
        == "OpenCobol2"
    )
    assert (
        _project_explorer_content(
            window,
        ).project
        is None
    )


def test_create_main_window_seeds_project_explorer_with_project(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    project_root = (
        tmp_path / "project"
    )
    project_root.mkdir()
    (
        project_root / "main.cbl"
    ).write_text(
        "x",
    )
    project = create_project(
        name="Demo",
        root_path=project_root,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )

    explorer = _project_explorer_content(
        window,
    )

    assert explorer.project is project
    assert (
        explorer._tree.topLevelItem(
            0,
        ).text(0)
        == "Demo"
    )


def test_create_main_window_uses_persisted_theme(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    settings_service.update_theme(
        ThemeSettings(
            active_theme_id="light",
        )
    )

    window = create_main_window(
        settings_service=settings_service,
    )

    assert (
        window.palette().color(
            QPalette.ColorRole.Window,
        ).name().upper()
        == "#FFFFFF"
    )


def test_create_main_window_menus_have_real_items(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )

    window = create_main_window(
        settings_service=settings_service,
    )

    file_menu = window.menus["file"]
    file_menu.aboutToShow.emit()

    titles = [
        action.text()
        for action in file_menu.actions()
    ]
    assert "New" in titles
    assert "Exit" in titles
