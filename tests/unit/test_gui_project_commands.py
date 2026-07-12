"""Unit tests for the New/Open/Save/Close Project command handlers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from opencobol2.gui.project_commands import (
    create_project_close_handler,
    create_project_from_details,
    create_project_new_handler,
    create_project_open_handler,
    create_project_save_as_handler,
    open_project_from_path,
    save_project_as,
)
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.project import (
    create_project,
    ProjectStorage,
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


def test_new_project_handler_cancelled_at_name_prompt(
    qapp,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_new_handler(
        project_explorer=explorer,
    )

    with patch(
        "opencobol2.gui.project_commands.QInputDialog.getText",
        return_value=(
            "",
            False,
        ),
    ):
        result = handler(
            None,
        )

    assert result is None
    assert explorer.project is None


def test_new_project_handler_cancelled_at_directory_prompt(
    qapp,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_new_handler(
        project_explorer=explorer,
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
            return_value="",
        ),
    ):
        result = handler(
            None,
        )

    assert result is None
    assert explorer.project is None


def test_new_project_handler_cancelled_at_save_prompt(
    qapp,
    tmp_path: Path,
) -> None:
    explorer = ProjectExplorerWidget()
    handler = create_project_new_handler(
        project_explorer=explorer,
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
                "",
                "",
            ),
        ),
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
        result = handler(
            None,
        )

    assert result is not None
    assert result.name == "Demo"
    assert explorer.project == result
    assert project_file.is_file()


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
