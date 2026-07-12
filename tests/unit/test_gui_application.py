"""Unit tests for the OpenCobol2 application bootstrap."""

from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

from PySide6.QtGui import QPalette

from opencobol2.gui.application import (
    create_main_window,
    TOP_LEVEL_MENUS,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.gui.settings_dialog import SettingsDialog
from opencobol2.project import (
    create_project,
    ProjectStorage,
)
from opencobol2.theming import LIGHT_THEME_ID
from opencobol2.settings import (
    SettingsService,
    SettingsStorage,
    ThemeSettings,
)


def _init_repository(
    path: Path,
) -> None:
    """Initialize a real, minimally-configured Git repository for testing."""

    subprocess.run(
        [
            "git",
            "init",
            "-q",
        ],
        cwd=path,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "test@example.com",
        ],
        cwd=path,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.name",
            "Test User",
        ],
        cwd=path,
        check=True,
    )


def _find_action(
    menu,
    title: str,
):
    # Materialize the actions list into a local before searching it: a
    # chained `next(a for a in menu.actions() if ...)` can let PySide6
    # garbage-collect the underlying QAction (and, for submenu actions, the
    # QMenu it owns) before the caller finishes using the returned value.
    actions = menu.actions()

    for action in actions:
        if action.text() == title:
            return action

    raise ValueError(
        f"No action titled {title!r} found."
    )


def _project_explorer_content(
    window,
) -> ProjectExplorerWidget:
    return (
        window.dock_manager.get_dock_widget(
            "project-explorer",
        ).widget()
    )


def _git_changes_content(
    window,
):
    return (
        window.dock_manager.get_dock_widget(
            "git-changes",
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


def test_open_and_close_project_menu_actions_work_end_to_end(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project_file = (
        tmp_path / "project.json"
    )
    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    window = create_main_window(
        settings_service=settings_service,
    )
    explorer = _project_explorer_content(
        window,
    )

    file_menu = window.menus["file"]
    file_menu.aboutToShow.emit()

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_file,
            ),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Open Project",
        ).trigger()

    assert (
        explorer.project is not None
        and explorer.project.name
        == "Demo"
    )

    file_menu.aboutToShow.emit()
    _find_action(
        file_menu,
        "Close Project",
    ).trigger()

    assert explorer.project is None


def test_new_and_save_project_as_menu_actions_work_end_to_end(
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
    explorer = _project_explorer_content(
        window,
    )

    file_menu = window.menus["file"]
    file_menu.aboutToShow.emit()
    # Bind the "New" action to a name before calling .menu() on it in a
    # separate statement: PySide6 has garbage-collected the submenu a
    # chained `_find_action(...).menu()` returned before it could be used.
    new_action = _find_action(
        file_menu,
        "New",
    )
    new_submenu = new_action.menu()
    new_submenu.aboutToShow.emit()

    project_file = (
        tmp_path / "project.json"
    )

    with (
        patch(
            "opencobol2.gui.project_commands.QInputDialog.getText",
            return_value=(
                "Demo",
                True,
            ),
        ),
        patch(
            "opencobol2.gui.project_commands."
            "QFileDialog.getExistingDirectory",
            return_value=str(
                tmp_path,
            ),
        ),
        patch(
            "opencobol2.gui.project_commands."
            "QFileDialog.getSaveFileName",
            return_value=(
                str(
                    project_file,
                ),
                "",
            ),
        ),
    ):
        _find_action(
            new_submenu,
            "New Project",
        ).trigger()

    assert (
        explorer.project is not None
        and explorer.project.name
        == "Demo"
    )

    file_menu.aboutToShow.emit()
    save_as_path = (
        tmp_path / "copy.json"
    )

    with patch(
        "opencobol2.gui.project_commands."
        "QFileDialog.getSaveFileName",
        return_value=(
            str(
                save_as_path,
            ),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Save Project As",
        ).trigger()

    assert save_as_path.is_file()


def test_status_bar_shows_no_project_and_default_theme(
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

    assert (
        window._status_bar_labels[
            "project"
        ].text()
        == "No Project Open"
    )
    assert (
        window._status_bar_labels[
            "theme"
        ].text()
        == "Theme: Dark"
    )


def test_status_bar_seeded_with_project_at_bootstrap(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )

    assert (
        window._status_bar_labels[
            "project"
        ].text()
        == "Project: Demo"
    )


def test_status_bar_updates_when_project_opened_and_closed(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project_file = (
        tmp_path / "project.json"
    )
    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    window = create_main_window(
        settings_service=settings_service,
    )
    project_label = (
        window._status_bar_labels[
            "project"
        ]
    )

    assert (
        project_label.text()
        == "No Project Open"
    )

    file_menu = window.menus["file"]
    file_menu.aboutToShow.emit()

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_file,
            ),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Open Project",
        ).trigger()

    assert (
        project_label.text()
        == "Project: Demo"
    )

    file_menu.aboutToShow.emit()
    _find_action(
        file_menu,
        "Close Project",
    ).trigger()

    assert (
        project_label.text()
        == "No Project Open"
    )


def test_status_bar_updates_when_theme_switches(
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
    theme_label = (
        window._status_bar_labels[
            "theme"
        ]
    )

    window._theme_service.set_active_theme(
        "light",
    )
    window.apply_active_theme()

    assert (
        theme_label.text()
        == "Theme: Light"
    )


def test_command_palette_menu_action_opens_dialog(
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

    view_menu = window.menus["view"]
    view_menu.aboutToShow.emit()
    palette_action = _find_action(
        view_menu,
        "Command Palette",
    )

    with patch(
        "opencobol2.gui.command_palette."
        "CommandPaletteDialog.exec",
        return_value=0,
    ) as mock_exec:
        palette_action.trigger()

    mock_exec.assert_called_once()


def test_git_changes_panel_empty_without_a_project(
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
    git_changes = _git_changes_content(
        window,
    )

    assert git_changes.repository_path is None


def test_git_changes_panel_seeded_with_project_repository(
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
    _init_repository(
        project_root,
    )
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
    git_changes = _git_changes_content(
        window,
    )

    assert (
        git_changes.repository_path
        == project_root
    )
    assert (
        git_changes._unstaged_list.count()
        == 1
    )


def test_git_changes_panel_updates_when_project_opened_and_closed(
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
    _init_repository(
        project_root,
    )
    project = create_project(
        name="Demo",
        root_path=project_root,
    )
    project_file = (
        tmp_path / "project.json"
    )
    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    window = create_main_window(
        settings_service=settings_service,
    )
    git_changes = _git_changes_content(
        window,
    )

    assert git_changes.repository_path is None

    file_menu = window.menus["file"]
    file_menu.aboutToShow.emit()

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_file,
            ),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Open Project",
        ).trigger()

    assert (
        git_changes.repository_path
        == project_root
    )

    file_menu.aboutToShow.emit()
    _find_action(
        file_menu,
        "Close Project",
    ).trigger()

    assert git_changes.repository_path is None


def test_git_changes_panel_falls_back_to_empty_for_non_repository_project(
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
    project = create_project(
        name="Demo",
        root_path=project_root,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    git_changes = _git_changes_content(
        window,
    )

    assert git_changes.repository_path is None


def test_settings_menu_action_applies_theme_to_running_window(
    qapp,
    tmp_path: Path,
) -> None:
    settings_path = (
        tmp_path / "settings.json"
    )
    settings_service = SettingsService(
        SettingsStorage(
            settings_path,
        )
    )

    window = create_main_window(
        settings_service=settings_service,
    )

    assert (
        window.palette().color(
            QPalette.ColorRole.Window,
        ).name().upper()
        == "#1E1E1E"
    )

    tools_menu = window.menus["tools"]
    tools_menu.aboutToShow.emit()
    settings_action = _find_action(
        tools_menu,
        "Settings",
    )

    def fake_exec(
        dialog_self,
    ):
        theme_index = (
            dialog_self._theme_combo.findData(
                LIGHT_THEME_ID,
            )
        )
        dialog_self._theme_combo.setCurrentIndex(
            theme_index,
        )
        dialog_self._apply_and_accept()
        return 1

    with patch.object(
        SettingsDialog,
        "exec",
        fake_exec,
    ):
        settings_action.trigger()

    assert (
        window.palette().color(
            QPalette.ColorRole.Window,
        ).name().upper()
        == "#FFFFFF"
    )
    assert (
        window._status_bar_labels[
            "theme"
        ].text()
        == "Theme: Light"
    )

    reloaded = SettingsService(
        SettingsStorage(
            settings_path,
        )
    )
    assert (
        reloaded.current.theme.active_theme_id
        == "light"
    )
