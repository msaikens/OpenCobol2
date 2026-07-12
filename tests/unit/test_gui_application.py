"""Unit tests for the OpenCobol2 application bootstrap."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QMessageBox

from opencobol2.compiler.providers import (
    CompilerProfile,
    CUSTOM_COMPILER_PROVIDER_ID,
)
from opencobol2.gui.application import (
    create_main_window,
    TOP_LEVEL_MENUS,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.gui.project_properties_dialog import (
    ProjectPropertiesDialog,
)
from opencobol2.gui.settings_dialog import SettingsDialog
from opencobol2.project import (
    create_project,
    ProjectStorage,
)
from opencobol2.theming import LIGHT_THEME_ID
from opencobol2.settings import (
    CompilerSettings,
    ExternalToolSettings,
    SettingsService,
    SettingsStorage,
    ThemeSettings,
)


_STUB_COMPILER_SCRIPT = '''
import sys

args = sys.argv[1:]
source = args[0]
output = args[args.index("-o") + 1]

with open(output, "w") as handle:
    handle.write("fake binary")

print(f"{source}:2:3: warning: unused data item", file=sys.stderr)
sys.exit(0)
'''


def _configure_stub_compiler_profile(
    settings_service: SettingsService,
    tmp_path: Path,
) -> None:
    """Configure a real subprocess stub compiler as the default profile.

    GnuCOBOL isn't guaranteed to be installed wherever these tests run, so
    this stands in for it via a real (non-mocked) subprocess invocation.
    """

    script = tmp_path / "stub_compiler.py"
    script.write_text(_STUB_COMPILER_SCRIPT)

    profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Stub Compiler",
        configuration={
            "executable_path": sys.executable,
            "compile_arguments": (
                str(script),
                "{source}",
                "-o",
                "{output}",
            ),
        },
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=profile.profile_id,
            profiles=(profile,),
        )
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


def _git_repository_content(
    window,
):
    return (
        window.dock_manager.get_dock_widget(
            "git-repository",
        ).widget()
    )


def _output_content(
    window,
):
    return (
        window.dock_manager.get_dock_widget(
            "output",
        ).widget()
    )


def _problems_content(
    window,
):
    return (
        window.dock_manager.get_dock_widget(
            "problems",
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


def test_settings_menu_action_applies_theme_to_open_editor_tabs(
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
    editor_tabs = window.centralWidget()
    editor_tabs.new_file()
    editor = editor_tabs.widget(0)

    assert (
        editor._line_number_color.name().upper()
        == "#858585"
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
        editor._line_number_color.name().upper()
        == "#237893"
    )
    assert (
        editor._current_line_color.name().upper()
        == "#F3F3F3"
    )

    # A tab opened after the switch must also use the new theme's colors.
    editor_tabs.new_file()
    new_editor = editor_tabs.widget(
        editor_tabs.count() - 1,
    )
    assert (
        new_editor._line_number_color.name().upper()
        == "#237893"
    )


def test_bootstrap_uses_configured_git_executable_path(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    configured_git = (
        tmp_path / "fake-git.exe"
    )
    settings_service.update_external_tools(
        ExternalToolSettings(
            git_executable_path=configured_git,
        )
    )

    window = create_main_window(
        settings_service=settings_service,
    )
    git_changes = _git_changes_content(
        window,
    )

    assert (
        git_changes._git_service.executable_path
        == str(configured_git)
    )


def test_settings_menu_action_applies_git_executable_path_to_running_window(
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

    assert (
        git_changes._git_service.executable_path
        == "git"
    )

    tools_menu = window.menus["tools"]
    tools_menu.aboutToShow.emit()
    settings_action = _find_action(
        tools_menu,
        "Settings",
    )
    new_git_path = str(
        tmp_path / "other-git.exe"
    )

    def fake_exec(
        dialog_self,
    ):
        dialog_self._git_executable_path_edit.setText(
            new_git_path,
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
        git_changes._git_service.executable_path
        == new_git_path
    )


def test_compiler_profiles_menu_action_opens_dialog(
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

    tools_menu = window.menus["tools"]
    tools_menu.aboutToShow.emit()
    profiles_action = _find_action(
        tools_menu,
        "Compiler Profiles",
    )

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "CompilerProfilesDialog.exec",
        return_value=0,
    ) as mock_exec:
        profiles_action.trigger()

    mock_exec.assert_called_once()


def test_compiler_profile_added_through_dialog_is_used_by_build_project(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    _configure_stub_compiler_profile(
        settings_service,
        tmp_path,
    )
    # Reset back to just the built-in default so the dialog is the only
    # thing that adds the custom profile, proving the composition (not a
    # profile that already happened to be configured beforehand).
    settings_service.update_compilers(
        CompilerSettings(),
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )

    tools_menu = window.menus["tools"]
    tools_menu.aboutToShow.emit()
    profiles_action = _find_action(
        tools_menu,
        "Compiler Profiles",
    )
    stub_script_path = (
        tmp_path / "stub_compiler.py"
    )
    stub_script_path.write_text(
        _STUB_COMPILER_SCRIPT,
    )

    def fake_exec(
        dialog_self,
    ):
        with patch(
            "opencobol2.gui.compiler_profiles_dialog."
            "QInputDialog.getItem",
            return_value=(
                "Custom local COBOL compiler",
                True,
            ),
        ):
            dialog_self._add_profile()

        dialog_self._display_name_edit.setText(
            "Dialog Configured Compiler",
        )
        dialog_self._field_widgets[
            "executable_path"
        ].setText(
            sys.executable,
        )
        dialog_self._field_widgets[
            "compile_arguments"
        ].setPlainText(
            f"{stub_script_path}\n{{source}}\n-o\n{{output}}",
        )
        dialog_self._set_selected_as_default()
        dialog_self._apply_and_accept()
        return 1

    with patch(
        "opencobol2.gui.compiler_profiles_dialog."
        "CompilerProfilesDialog.exec",
        fake_exec,
    ):
        profiles_action.trigger()

    assert (
        settings_service.current.compilers
        .default_profile.display_name
        == "Dialog Configured Compiler"
    )

    output_widget = _output_content(
        window,
    )
    build_menu = window.menus["build"]
    build_menu.aboutToShow.emit()
    _find_action(
        build_menu,
        "Build Project",
    ).trigger()

    assert (
        "main.cbl: succeeded"
        in output_widget.toPlainText()
    )


def test_project_properties_selects_a_project_specific_compiler_profile(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    stub_script = tmp_path / "stub_compiler.py"
    stub_script.write_text(
        _STUB_COMPILER_SCRIPT,
    )
    project_profile = CompilerProfile(
        provider_id=CUSTOM_COMPILER_PROVIDER_ID,
        display_name="Project-Specific Compiler",
        configuration={
            "executable_path": sys.executable,
            "compile_arguments": (
                str(stub_script),
                "{source}",
                "-o",
                "{output}",
            ),
        },
    )
    existing_compilers = (
        settings_service.current.compilers
    )
    settings_service.update_compilers(
        CompilerSettings(
            default_profile_id=(
                existing_compilers.default_profile_id
            ),
            profiles=(
                *existing_compilers.profiles,
                project_profile,
            ),
        )
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    explorer = _project_explorer_content(
        window,
    )

    def fake_exec(
        dialog_self,
    ):
        index = (
            dialog_self._compiler_profile_combo.findData(
                project_profile.profile_id,
            )
        )
        dialog_self._compiler_profile_combo.setCurrentIndex(
            index,
        )
        dialog_self._apply_and_accept()
        return 1

    # The context menu's own QMenu.exec() hangs indefinitely under the
    # offscreen platform and can't be mocked (a known Qt/PySide6 quirk), so
    # this triggers the same signal a real "Properties..." click would
    # rather than driving the menu itself.
    with patch(
        "opencobol2.gui.project_properties_dialog."
        "ProjectPropertiesDialog.exec",
        fake_exec,
    ):
        explorer.project_properties_requested.emit()

    assert (
        explorer.project.properties
        .default_compiler_profile_id
        == project_profile.profile_id
    )

    output_widget = _output_content(
        window,
    )
    build_menu = window.menus["build"]
    build_menu.aboutToShow.emit()
    _find_action(
        build_menu,
        "Build Project",
    ).trigger()

    assert (
        "main.cbl: succeeded"
        in output_widget.toPlainText()
    )


def test_edit_menu_find_and_replace_actions_work_end_to_end(
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
    editor_tabs = window.centralWidget()
    editor_tabs.new_file()
    editor = editor_tabs.widget(0)
    editor.setPlainText(
        "needle in a haystack, "
        "another needle here",
    )

    edit_menu = window.menus["edit"]
    edit_menu.aboutToShow.emit()
    _find_action(
        edit_menu,
        "Find",
    ).trigger()

    assert not editor._find_bar.isHidden()
    assert (
        editor._find_bar._replace_row_widget.isHidden()
    )

    edit_menu.aboutToShow.emit()
    _find_action(
        edit_menu,
        "Replace",
    ).trigger()

    assert (
        not editor._find_bar._replace_row_widget.isHidden()
    )

    editor._find_bar.find_edit.setText(
        "needle",
    )
    editor._find_bar.replace_edit.setText(
        "pin",
    )
    editor._find_bar._handle_replace_all()

    assert (
        editor.toPlainText()
        == "pin in a haystack, another pin here"
    )


def test_main_window_central_widget_is_editor_tabs(
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
        type(
            window.centralWidget(),
        ).__name__
        == "EditorTabsWidget"
    )
    assert window.centralWidget().count() == 0


def test_double_clicking_project_file_opens_it_in_editor(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    explorer = _project_explorer_content(
        window,
    )
    editor_tabs = window.centralWidget()

    root_item = explorer._tree.topLevelItem(
        0,
    )
    file_item = root_item.child(
        0,
    )
    explorer._handle_item_double_clicked(
        file_item,
        0,
    )

    assert editor_tabs.count() == 1
    assert (
        editor_tabs.tabText(0)
        == "main.cbl"
    )
    assert (
        editor_tabs.widget(0).toPlainText()
        == "IDENTIFICATION DIVISION.\n"
    )


def test_opened_cbl_file_is_syntax_highlighted_end_to_end(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       IDENTIFICATION DIVISION.\n",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    explorer = _project_explorer_content(
        window,
    )
    editor_tabs = window.centralWidget()

    root_item = explorer._tree.topLevelItem(
        0,
    )
    file_item = root_item.child(
        0,
    )
    explorer._handle_item_double_clicked(
        file_item,
        0,
    )

    editor = editor_tabs.widget(
        0,
    )
    block = editor.document().findBlockByNumber(
        0,
    )
    colors = {
        block.text()[
            format_range.start:format_range.start
            + format_range.length
        ]: format_range.format.foreground()
        .color()
        .name()
        for format_range in block.layout().formats()
    }

    assert colors["IDENTIFICATION"] == "#569cd6"
    assert colors["DIVISION"] == "#569cd6"


def test_file_menu_new_open_save_actions_work_end_to_end(
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
    editor_tabs = window.centralWidget()

    file_menu = window.menus["file"]
    file_menu.aboutToShow.emit()
    new_action = _find_action(
        file_menu,
        "New",
    )
    new_submenu = new_action.menu()
    new_submenu.aboutToShow.emit()
    _find_action(
        new_submenu,
        "New File",
    ).trigger()

    assert editor_tabs.count() == 1
    assert (
        editor_tabs.tabText(0)
        == "Untitled"
    )

    editor_tabs.widget(0).setPlainText(
        "hello",
    )
    save_path = (
        tmp_path / "new.cbl"
    )

    file_menu.aboutToShow.emit()
    with patch(
        "opencobol2.gui.editor.QFileDialog.getSaveFileName",
        return_value=(
            str(save_path),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Save",
        ).trigger()

    assert save_path.read_text() == "hello"
    assert (
        editor_tabs.tabText(0)
        == "new.cbl"
    )

    other_file = tmp_path / "existing.cbl"
    other_file.write_text(
        "x",
    )
    file_menu.aboutToShow.emit()
    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(other_file),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Open File",
        ).trigger()

    assert editor_tabs.count() == 2
    assert (
        editor_tabs.tabText(1)
        == "existing.cbl"
    )

    file_menu.aboutToShow.emit()
    _find_action(
        file_menu,
        "Save All",
    ).trigger()

    file_menu.aboutToShow.emit()
    with patch(
        "opencobol2.gui.editor.QMessageBox.question",
        return_value=(
            QMessageBox.StandardButton.Discard
        ),
    ):
        _find_action(
            file_menu,
            "Close All Files",
        ).trigger()

    assert editor_tabs.count() == 0


def test_git_repository_panel_empty_without_a_project(
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
    git_repository = _git_repository_content(
        window,
    )

    assert git_repository.repository_path is None


def test_git_repository_panel_seeded_with_project_repository(
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
    subprocess.run(
        [
            "git",
            "add",
            ".",
        ],
        cwd=project_root,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "commit",
            "-q",
            "-m",
            "Initial commit",
        ],
        cwd=project_root,
        check=True,
    )
    project = create_project(
        name="Demo",
        root_path=project_root,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    git_repository = _git_repository_content(
        window,
    )

    assert (
        git_repository.repository_path
        == project_root
    )
    assert (
        git_repository._history_list.count()
        == 1
    )


def test_git_repository_panel_updates_when_project_opened_and_closed(
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
    git_repository = _git_repository_content(
        window,
    )

    assert git_repository.repository_path is None

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
        git_repository.repository_path
        == project_root
    )

    file_menu.aboutToShow.emit()
    _find_action(
        file_menu,
        "Close Project",
    ).trigger()

    assert git_repository.repository_path is None


def test_recent_projects_menu_lists_and_reopens_projects(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )

    project_one = create_project(
        name="ProjectOne",
        root_path=tmp_path,
    )
    project_two = create_project(
        name="ProjectTwo",
        root_path=tmp_path,
    )
    project_one_file = (
        tmp_path / "one.json"
    )
    project_two_file = (
        tmp_path / "two.json"
    )
    ProjectStorage(
        project_one_file,
    ).save(
        project_one,
    )
    ProjectStorage(
        project_two_file,
    ).save(
        project_two,
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
                project_one_file,
            ),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Open Project",
        ).trigger()

    file_menu.aboutToShow.emit()
    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_two_file,
            ),
            "",
        ),
    ):
        _find_action(
            file_menu,
            "Open Project",
        ).trigger()

    # Newest-first: ProjectTwo was opened last.
    assert (
        settings_service.current.recent_projects.paths
        == (
            project_two_file,
            project_one_file,
        )
    )

    file_menu.aboutToShow.emit()
    recent_item = _find_action(
        file_menu,
        str(
            project_one_file,
        ),
    )
    recent_item.trigger()

    assert explorer.project.name == "ProjectOne"
    # Reopening ProjectOne moves it back to the front.
    assert (
        settings_service.current.recent_projects.paths
        == (
            project_one_file,
            project_two_file,
        )
    )


def test_build_project_menu_action_compiles_project_end_to_end(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )
    _configure_stub_compiler_profile(
        settings_service,
        tmp_path,
    )
    (
        tmp_path / "main.cbl"
    ).write_text(
        "IDENTIFICATION DIVISION.\n",
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    window = create_main_window(
        settings_service=settings_service,
        project=project,
    )
    output_widget = _output_content(
        window,
    )
    problems_widget = _problems_content(
        window,
    )

    build_menu = window.menus["build"]
    build_menu.aboutToShow.emit()
    _find_action(
        build_menu,
        "Build Project",
    ).trigger()

    assert (
        "main.cbl: succeeded"
        in output_widget.toPlainText()
    )
    assert problems_widget.rowCount() == 1
    assert (
        problems_widget.item(
            0,
            0,
        ).text()
        == "WARNING"
    )
    assert (
        tmp_path
        / project.properties.output_directory
        / "main"
    ).is_file()
