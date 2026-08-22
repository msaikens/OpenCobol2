"""Unit tests for the New/Open/Save/Close Project command handlers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from opencobol2.commands import CommandContext
from opencobol2.commands.builtins import BuiltInCommandIds
from opencobol2.gui.new_project_dialog import NewProjectDialog
from opencobol2.gui.project_commands import (
    create_delete_path_handler,
    create_new_file_handler,
    create_new_folder_handler,
    create_project_close_handler,
    create_project_from_details,
    create_project_new_handler,
    create_project_open_handler,
    create_project_open_recent_handler,
    create_project_save_as_handler,
    create_recent_project_provider,
    create_rename_path_handler,
    open_project_from_path,
    record_recent_project,
    save_project_as,
)
from opencobol2.gui.editor import EditorTabsWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.documents import DocumentService
from opencobol2.project import (
    create_project,
    ProjectStorage,
)
from opencobol2.settings import (
    SettingsService,
    SettingsStorage,
)


def test_open_project_from_path_loads_and_displays_project(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project_file = tmp_path / "project.json"
    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    explorer = ProjectExplorerWidget()

    loaded = open_project_from_path(
        explorer,
        project_file,
    )

    assert loaded.name == "Demo"
    assert explorer.project == loaded


def test_open_handler_does_nothing_when_dialog_is_cancelled(
    qapp,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_open_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            "",
            "",
        ),
    ):
        result = handler(
            None,
        )

    assert result is None
    assert explorer.project is None


def test_open_handler_loads_project_from_selected_path(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project_file = tmp_path / "project.json"
    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    explorer = ProjectExplorerWidget()
    handler = create_project_open_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_file,
            ),
            "",
        ),
    ):
        result = handler(
            None,
        )

    assert result is not None
    assert result.name == "Demo"
    assert explorer.project == result


def test_open_handler_records_the_opened_path_in_the_holder(
    qapp,
    tmp_path: Path,
) -> None:
    # Editor §ProjectPanels-1: this is what lets Project Properties
    # save its changes back to the right file -- nothing tracked
    # which file the open project came from before this existed.
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    project_file = tmp_path / "project.json"
    ProjectStorage(
        project_file,
    ).save(
        project,
    )

    explorer = ProjectExplorerWidget()
    project_file_path_holder: list[Path | None] = [
        None,
    ]
    handler = create_project_open_handler(
        project_explorer=explorer,
        project_file_path_holder=project_file_path_holder,
    )

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_file,
            ),
            "",
        ),
    ):
        handler(
            None,
        )

    assert project_file_path_holder[0] == project_file


def test_open_handler_reports_error_for_missing_project_file(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_open_handler(
        project_explorer=explorer,
    )
    missing_path = (
        tmp_path / "missing.json"
    )

    with (
        patch(
            "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
            return_value=(
                str(
                    missing_path,
                ),
                "",
            ),
        ),
        patch(
            "opencobol2.gui.project_commands.QMessageBox.critical",
        ) as mock_critical,
    ):
        result = handler(
            None,
        )

    assert result is None
    assert explorer.project is None
    mock_critical.assert_called_once()


def test_open_handler_reports_error_for_malformed_project_file(
    qapp,
    tmp_path: Path,
) -> None:
    project_file = (
        tmp_path / "project.json"
    )
    project_file.write_text(
        "not valid json",
        encoding="utf-8",
    )

    explorer = ProjectExplorerWidget()
    handler = create_project_open_handler(
        project_explorer=explorer,
    )

    with (
        patch(
            "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
            return_value=(
                str(
                    project_file,
                ),
                "",
            ),
        ),
        patch(
            "opencobol2.gui.project_commands.QMessageBox.critical",
        ) as mock_critical,
    ):
        result = handler(
            None,
        )

    assert result is None
    assert explorer.project is None
    mock_critical.assert_called_once()


def test_open_handler_uses_parent_widget_provider(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget()
    sentinel_parent = object()
    handler = create_project_open_handler(
        project_explorer=explorer,
        parent_widget_provider=(
            lambda: sentinel_parent
        ),
    )

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            "",
            "",
        ),
    ) as mock_dialog:
        handler(
            None,
        )

    assert (
        mock_dialog.call_args.args[0]
        is sentinel_parent
    )


def test_close_handler_clears_project(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    handler = create_project_close_handler(
        project_explorer=explorer,
    )

    handler(
        None,
    )

    assert explorer.project is None


def test_close_handler_clears_the_recorded_project_path(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    project_file_path_holder: list[Path | None] = [
        tmp_path / "project.json",
    ]
    handler = create_project_close_handler(
        project_explorer=explorer,
        project_file_path_holder=project_file_path_holder,
    )

    handler(
        None,
    )

    assert project_file_path_holder[0] is None


def test_create_project_from_details_creates_and_persists(
    qapp,
    tmp_path: Path,
) -> None:
    project_file = (
        tmp_path / "project.json"
    )

    project = create_project_from_details(
        "Demo",
        tmp_path,
        project_file,
    )

    assert project.name == "Demo"
    assert project_file.is_file()
    assert (
        ProjectStorage(
            project_file,
        ).load()
        == project
    )


def test_save_project_as_persists_to_new_location(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    new_path = (
        tmp_path / "copy.json"
    )

    result = save_project_as(
        project,
        new_path,
    )

    assert result == project
    assert new_path.is_file()
    assert (
        ProjectStorage(
            new_path,
        ).load()
        == project
    )


def _fake_new_project_dialog_exec(
    name: str,
    root_path: Path,
):
    """Build a fake `NewProjectDialog.exec` that fills in and accepts the form.

    Mirrors the established pattern for testing a real `QDialog.exec()`
    flow without opening an actual blocking modal (see
    `SettingsDialog`/`CompilerProfilesDialog`'s own tests): patched in
    as a replacement for the bound method, so it receives the dialog
    instance as its first argument.
    """

    def fake_exec(
        dialog_self,
    ):
        dialog_self._name_edit.setText(
            name,
        )
        dialog_self._root_edit.setText(
            str(
                root_path,
            ),
        )
        dialog_self._validate_and_accept()

        return int(
            dialog_self.result(),
        )

    return fake_exec


def _fake_cancelled_new_project_dialog_exec(
    dialog_self,
) -> int:
    """A fake `NewProjectDialog.exec` that immediately cancels the form."""

    dialog_self.reject()

    return int(
        dialog_self.result(),
    )


def test_new_project_handler_cancelled_returns_none(
    qapp,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_new_handler(
        project_explorer=explorer,
    )

    with patch.object(
        NewProjectDialog,
        "exec",
        _fake_cancelled_new_project_dialog_exec,
    ):
        result = handler(
            None,
        )

    assert result is None
    assert explorer.project is None


def test_new_project_handler_creates_project_end_to_end(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_new_handler(
        project_explorer=explorer,
    )
    root_path = (
        tmp_path / "Demo"
    )

    with patch.object(
        NewProjectDialog,
        "exec",
        _fake_new_project_dialog_exec(
            "Demo",
            root_path,
        ),
    ):
        result = handler(
            None,
        )

    assert result is not None
    assert result.name == "Demo"
    assert explorer.project == result
    assert (
        root_path / "Demo.ocproj"
    ).is_file()


def test_new_project_handler_creates_the_root_directory_if_missing(
    qapp,
    tmp_path: Path,
) -> None:
    """The root directory field can point at a location that doesn't
    exist yet (its default suggestion always does, on a fresh
    install) -- the handler must create it rather than fail."""

    explorer = ProjectExplorerWidget()
    handler = create_project_new_handler(
        project_explorer=explorer,
    )
    root_path = (
        tmp_path / "does-not-exist-yet" / "Demo"
    )
    assert not root_path.exists()

    with patch.object(
        NewProjectDialog,
        "exec",
        _fake_new_project_dialog_exec(
            "Demo",
            root_path,
        ),
    ):
        result = handler(
            None,
        )

    assert result is not None
    assert root_path.is_dir()


def test_new_project_handler_records_the_created_path_in_the_holder(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget()
    project_file_path_holder: list[Path | None] = [
        None,
    ]
    handler = create_project_new_handler(
        project_explorer=explorer,
        project_file_path_holder=project_file_path_holder,
    )
    root_path = (
        tmp_path / "Demo"
    )

    with patch.object(
        NewProjectDialog,
        "exec",
        _fake_new_project_dialog_exec(
            "Demo",
            root_path,
        ),
    ):
        handler(
            None,
        )

    assert project_file_path_holder[0] == (
        root_path / "Demo.ocproj"
    )


def test_save_as_handler_shows_information_when_no_project_open(
    qapp,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_save_as_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QMessageBox.information",
    ) as mock_information:
        result = handler(
            None,
        )

    assert result is None
    mock_information.assert_called_once()


def test_save_as_handler_cancelled_dialog_leaves_project_unchanged(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    handler = create_project_save_as_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands."
        "QFileDialog.getSaveFileName",
        return_value=(
            "",
            "",
        ),
    ):
        result = handler(
            None,
        )

    assert result is None
    assert explorer.project is project


def test_save_as_handler_persists_current_project_to_new_path(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    handler = create_project_save_as_handler(
        project_explorer=explorer,
    )
    new_path = (
        tmp_path / "copy.json"
    )

    with patch(
        "opencobol2.gui.project_commands."
        "QFileDialog.getSaveFileName",
        return_value=(
            str(
                new_path,
            ),
            "",
        ),
    ):
        result = handler(
            None,
        )

    assert result == project
    assert new_path.is_file()


def test_save_as_handler_records_the_new_path_in_the_holder(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    project_file_path_holder: list[Path | None] = [
        tmp_path / "original.json",
    ]
    handler = create_project_save_as_handler(
        project_explorer=explorer,
        project_file_path_holder=project_file_path_holder,
    )
    new_path = (
        tmp_path / "copy.json"
    )

    with patch(
        "opencobol2.gui.project_commands."
        "QFileDialog.getSaveFileName",
        return_value=(
            str(
                new_path,
            ),
            "",
        ),
    ):
        handler(
            None,
        )

    assert project_file_path_holder[0] == new_path


def test_save_as_handler_reports_error_on_save_failure(
    qapp,
    tmp_path: Path,
) -> None:
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    handler = create_project_save_as_handler(
        project_explorer=explorer,
    )
    # ProjectStorage.save() auto-creates missing parent directories, so to
    # force an OSError, put a *file* where a directory needs to exist.
    blocker_path = (
        tmp_path / "blocker"
    )
    blocker_path.write_text(
        "x",
        encoding="utf-8",
    )
    bad_path = (
        blocker_path / "copy.json"
    )

    with (
        patch(
            "opencobol2.gui.project_commands."
            "QFileDialog.getSaveFileName",
            return_value=(
                str(
                    bad_path,
                ),
                "",
            ),
        ),
        patch(
            "opencobol2.gui.project_commands.QMessageBox.critical",
        ) as mock_critical,
    ):
        result = handler(
            None,
        )

    assert result is None
    mock_critical.assert_called_once()


def _build_settings_service(
    tmp_path: Path,
) -> SettingsService:
    return SettingsService(
        SettingsStorage(
            tmp_path / "settings.json",
        )
    )


def test_record_recent_project_moves_path_to_front(
    tmp_path: Path,
) -> None:
    settings_service = _build_settings_service(
        tmp_path,
    )
    first_path = (
        tmp_path / "first.json"
    )
    second_path = (
        tmp_path / "second.json"
    )

    record_recent_project(
        settings_service,
        first_path,
    )
    record_recent_project(
        settings_service,
        second_path,
    )
    record_recent_project(
        settings_service,
        first_path,
    )

    assert (
        settings_service.current.recent_projects.paths
        == (
            first_path,
            second_path,
        )
    )


def test_recent_project_provider_lists_only_existing_files(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = _build_settings_service(
        tmp_path,
    )
    existing_path = (
        tmp_path / "exists.json"
    )
    existing_path.write_text(
        "{}",
        encoding="utf-8",
    )
    missing_path = (
        tmp_path / "missing.json"
    )

    record_recent_project(
        settings_service,
        missing_path,
    )
    record_recent_project(
        settings_service,
        existing_path,
    )

    provider = create_recent_project_provider(
        settings_service,
    )
    items = tuple(
        provider(
            CommandContext(),
        )
    )

    # existing_path holds "{}" (not a real, loadable project), so its
    # title falls back to the file's own stem -- the point of this
    # test is the existence filter, not name resolution, which has
    # its own dedicated test below.
    assert len(items) == 1
    assert items[0].title == "exists"
    assert (
        items[0].command_id
        == BuiltInCommandIds.PROJECT_OPEN_RECENT
    )
    assert items[0].context.get(
        "path",
    ) == str(
        existing_path,
    )


def test_recent_project_provider_shows_the_projects_own_name(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = _build_settings_service(
        tmp_path,
    )
    project = create_project(
        name="My Real Project",
        root_path=tmp_path,
    )
    project_file = (
        tmp_path / "whatever-i-named-it.ocproj"
    )
    ProjectStorage(
        project_file,
    ).save(
        project,
    )
    record_recent_project(
        settings_service,
        project_file,
    )

    provider = create_recent_project_provider(
        settings_service,
    )
    items = tuple(
        provider(
            CommandContext(),
        )
    )

    assert len(items) == 1
    assert items[0].title == "My Real Project"


def test_open_recent_handler_opens_project_and_re_records(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = _build_settings_service(
        tmp_path,
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
    record_recent_project(
        settings_service,
        project_file,
    )

    explorer = ProjectExplorerWidget()
    handler = create_project_open_recent_handler(
        project_explorer=explorer,
        settings_service=settings_service,
    )

    result = handler(
        CommandContext(
            values={
                "path": str(
                    project_file,
                ),
            },
        )
    )

    assert result is not None
    assert result.name == "Demo"
    assert explorer.project == result
    assert (
        settings_service.current.recent_projects.paths[
            0
        ]
        == project_file
    )


def test_open_recent_handler_records_the_opened_path_in_the_holder(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = _build_settings_service(
        tmp_path,
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

    explorer = ProjectExplorerWidget()
    project_file_path_holder: list[Path | None] = [
        None,
    ]
    handler = create_project_open_recent_handler(
        project_explorer=explorer,
        settings_service=settings_service,
        project_file_path_holder=project_file_path_holder,
    )

    handler(
        CommandContext(
            values={
                "path": str(
                    project_file,
                ),
            },
        )
    )

    assert project_file_path_holder[0] == project_file


def test_open_recent_handler_reports_error_for_missing_file(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = _build_settings_service(
        tmp_path,
    )
    missing_path = (
        tmp_path / "missing.json"
    )

    explorer = ProjectExplorerWidget()
    handler = create_project_open_recent_handler(
        project_explorer=explorer,
        settings_service=settings_service,
    )

    with patch(
        "opencobol2.gui.project_commands.QMessageBox.critical",
    ) as mock_critical:
        result = handler(
            CommandContext(
                values={
                    "path": str(
                        missing_path,
                    ),
                },
            )
        )

    assert result is None
    mock_critical.assert_called_once()
    assert explorer.project is None


def test_open_handler_records_recent_project_when_settings_service_given(
    qapp,
    tmp_path: Path,
) -> None:
    settings_service = _build_settings_service(
        tmp_path,
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

    explorer = ProjectExplorerWidget()
    handler = create_project_open_handler(
        project_explorer=explorer,
        settings_service=settings_service,
    )

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_file,
            ),
            "",
        ),
    ):
        handler(
            None,
        )

    assert (
        settings_service.current.recent_projects.paths
        == (
            project_file,
        )
    )


def test_open_handler_without_settings_service_does_not_record(
    qapp,
    tmp_path: Path,
) -> None:
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

    explorer = ProjectExplorerWidget()
    handler = create_project_open_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QFileDialog.getOpenFileName",
        return_value=(
            str(
                project_file,
            ),
            "",
        ),
    ):
        result = handler(
            None,
        )

    assert result is not None


# --- New File.../New Folder... (Project Explorer context menu) -------


def _build_editor_tabs(
    tmp_path: Path,
) -> EditorTabsWidget:
    from opencobol2.theming import (
        create_builtin_theme_registry,
        DARK_THEME_ID,
    )

    return EditorTabsWidget(
        document_service=DocumentService(),
        theme=create_builtin_theme_registry().get(
            DARK_THEME_ID,
        ),
    )


def test_new_file_handler_creates_and_opens_the_file(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    editor_tabs = _build_editor_tabs(
        tmp_path,
    )
    handler = create_new_file_handler(
        project_explorer=explorer,
        editor_tabs_widget=editor_tabs,
    )

    with patch(
        "opencobol2.gui.project_commands.prompt_for_text",
        return_value=(
            "hello.cbl",
            True,
        ),
    ):
        handler(
            tmp_path,
        )

    assert (
        tmp_path / "hello.cbl"
    ).is_file()
    assert editor_tabs.count() == 1


def test_new_file_handler_defaults_to_cbl_extension_when_none_given(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    editor_tabs = _build_editor_tabs(
        tmp_path,
    )
    handler = create_new_file_handler(
        project_explorer=explorer,
        editor_tabs_widget=editor_tabs,
    )

    with patch(
        "opencobol2.gui.project_commands.prompt_for_text",
        return_value=(
            "hello",
            True,
        ),
    ):
        handler(
            tmp_path,
        )

    assert (
        tmp_path / "hello.cbl"
    ).is_file()


def test_new_file_handler_respects_an_explicit_extension(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    editor_tabs = _build_editor_tabs(
        tmp_path,
    )
    handler = create_new_file_handler(
        project_explorer=explorer,
        editor_tabs_widget=editor_tabs,
    )

    with patch(
        "opencobol2.gui.project_commands.prompt_for_text",
        return_value=(
            "notes.txt",
            True,
        ),
    ):
        handler(
            tmp_path,
        )

    assert (
        tmp_path / "notes.txt"
    ).is_file()
    assert not (
        tmp_path / "notes.txt.cbl"
    ).exists()


def test_new_file_handler_cancelled_creates_nothing(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    editor_tabs = _build_editor_tabs(
        tmp_path,
    )
    handler = create_new_file_handler(
        project_explorer=explorer,
        editor_tabs_widget=editor_tabs,
    )

    with patch(
        "opencobol2.gui.project_commands.prompt_for_text",
        return_value=(
            "",
            False,
        ),
    ):
        handler(
            tmp_path,
        )

    assert list(
        tmp_path.iterdir(),
    ) == []
    assert editor_tabs.count() == 0


def test_new_file_handler_refuses_to_overwrite_an_existing_file(
    qapp,
    tmp_path: Path,
) -> None:
    existing = tmp_path / "already-here.cbl"
    existing.write_text(
        "ORIGINAL",
    )
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    editor_tabs = _build_editor_tabs(
        tmp_path,
    )
    handler = create_new_file_handler(
        project_explorer=explorer,
        editor_tabs_widget=editor_tabs,
    )

    with (
        patch(
            "opencobol2.gui.project_commands.prompt_for_text",
            return_value=(
                "already-here.cbl",
                True,
            ),
        ),
        patch(
            "opencobol2.gui.project_commands.QMessageBox.critical",
        ) as mock_critical,
    ):
        handler(
            tmp_path,
        )

    mock_critical.assert_called_once()
    assert existing.read_text() == "ORIGINAL"


def test_new_folder_handler_creates_the_folder(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    handler = create_new_folder_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.prompt_for_text",
        return_value=(
            "Subfolder",
            True,
        ),
    ):
        handler(
            tmp_path,
        )

    assert (
        tmp_path / "Subfolder"
    ).is_dir()


def test_project_explorer_context_menu_offers_new_file_and_folder(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )

    menu = explorer.build_root_context_menu()

    action_texts = [
        action.text()
        for action in menu.actions()
    ]
    assert "New File..." in action_texts
    assert "New Folder..." in action_texts
    assert "Properties..." in action_texts


def test_rename_path_handler_renames_a_file(
    qapp,
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.cbl"
    original.write_text(
        "x",
    )
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    handler = create_rename_path_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.prompt_for_text",
        return_value=(
            "renamed.cbl",
            True,
        ),
    ):
        handler(
            original,
        )

    assert not original.exists()
    assert (
        tmp_path / "renamed.cbl"
    ).is_file()


def test_rename_path_handler_does_nothing_when_cancelled(
    qapp,
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.cbl"
    original.write_text(
        "x",
    )
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    handler = create_rename_path_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.prompt_for_text",
        return_value=(
            "renamed.cbl",
            False,
        ),
    ):
        handler(
            original,
        )

    assert original.is_file()
    assert not (
        tmp_path / "renamed.cbl"
    ).exists()


def test_rename_path_handler_reports_an_error_when_the_new_name_already_exists(
    qapp,
    tmp_path: Path,
) -> None:
    original = tmp_path / "original.cbl"
    original.write_text(
        "x",
    )
    (
        tmp_path / "taken.cbl"
    ).write_text(
        "y",
    )
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    handler = create_rename_path_handler(
        project_explorer=explorer,
    )

    with (
        patch(
            "opencobol2.gui.project_commands.prompt_for_text",
            return_value=(
                "taken.cbl",
                True,
            ),
        ),
        patch(
            "opencobol2.gui.project_commands.QMessageBox.critical",
        ) as mock_critical,
    ):
        handler(
            original,
        )

    mock_critical.assert_called_once()
    assert original.is_file()


def test_delete_path_handler_deletes_a_file_when_confirmed(
    qapp,
    tmp_path: Path,
) -> None:
    target = tmp_path / "doomed.cbl"
    target.write_text(
        "x",
    )
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    handler = create_delete_path_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        handler(
            target,
        )

    assert not target.exists()


def test_delete_path_handler_deletes_a_folder_and_its_contents_when_confirmed(
    qapp,
    tmp_path: Path,
) -> None:
    target = tmp_path / "doomed_folder"
    target.mkdir()
    (
        target / "inner.cbl"
    ).write_text(
        "x",
    )
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    handler = create_delete_path_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        handler(
            target,
        )

    assert not target.exists()


def test_delete_path_handler_does_nothing_when_not_confirmed(
    qapp,
    tmp_path: Path,
) -> None:
    target = tmp_path / "safe.cbl"
    target.write_text(
        "x",
    )
    explorer = ProjectExplorerWidget(
        create_project(
            name="Demo",
            root_path=tmp_path,
        )
    )
    handler = create_delete_path_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        handler(
            target,
        )

    assert target.is_file()
