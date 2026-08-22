"""Unit tests for the Find-in-Files search and command handler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from opencobol2.gui.find_results_panel import FindResultsWidget
from opencobol2.gui.project_explorer import ProjectExplorerWidget
from opencobol2.gui.search_commands import (
    create_find_in_files_handler,
    create_find_in_path_handler,
    search_project_for_text,
)
from opencobol2.project import create_project


def test_search_finds_every_matching_line_case_insensitively(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO Y.\n"
        "       display x.\n"
        "       ADD 1 TO Z.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    results = search_project_for_text(
        project,
        "X",
    )

    assert len(results) == 2
    assert results[0].line == 1
    assert results[0].column == 13
    assert results[0].line_text == "MOVE X TO Y."
    assert results[1].line == 2
    assert results[1].column == 16


def test_search_finds_multiple_matches_on_one_line(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO X.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    results = search_project_for_text(
        project,
        "X",
    )

    assert [result.column for result in results] == [
        13,
        18,
    ]


def test_search_with_empty_query_returns_nothing(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO Y.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    assert (
        search_project_for_text(
            project,
            "",
        )
        == ()
    )


def test_search_skips_unreadable_files(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO Y.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    with patch(
        "pathlib.Path.read_text",
        side_effect=OSError(
            "boom",
        ),
    ):
        results = search_project_for_text(
            project,
            "X",
        )

    assert results == ()


def test_search_with_a_directory_scope_only_finds_matches_under_it(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO Y.\n"
    )
    subfolder = tmp_path / "sub"
    subfolder.mkdir()
    (
        subfolder / "inner.cbl"
    ).write_text(
        "       MOVE X TO Z.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    results = search_project_for_text(
        project,
        "X",
        scope=subfolder,
    )

    assert len(results) == 1
    assert results[0].path == (
        subfolder / "inner.cbl"
    )


def test_search_with_a_file_scope_only_finds_matches_in_that_file(
    qapp,
    tmp_path: Path,
) -> None:
    first = tmp_path / "main.cbl"
    first.write_text(
        "       MOVE X TO Y.\n"
    )
    (
        tmp_path / "other.cbl"
    ).write_text(
        "       MOVE X TO Z.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )

    results = search_project_for_text(
        project,
        "X",
        scope=first,
    )

    assert len(results) == 1
    assert results[0].path == first


def test_find_in_path_handler_scopes_the_search_to_the_given_path(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO Y.\n"
    )
    subfolder = tmp_path / "sub"
    subfolder.mkdir()
    (
        subfolder / "inner.cbl"
    ).write_text(
        "       MOVE X TO Z.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    find_results_widget = FindResultsWidget()
    revealed = []
    handler = create_find_in_path_handler(
        project_explorer=explorer,
        find_results_widget=find_results_widget,
        reveal_find_results=lambda: revealed.append(
            True,
        ),
    )

    with patch(
        "opencobol2.gui.search_commands.prompt_for_text",
        return_value=(
            "X",
            True,
        ),
    ):
        result = handler(
            subfolder,
        )

    assert len(result) == 1
    assert result[0].path == (
        subfolder / "inner.cbl"
    )
    assert revealed == [True]
    assert find_results_widget.rowCount() == 1


def test_find_in_path_handler_does_nothing_when_cancelled(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO Y.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    find_results_widget = FindResultsWidget()
    handler = create_find_in_path_handler(
        project_explorer=explorer,
        find_results_widget=find_results_widget,
    )

    with patch(
        "opencobol2.gui.search_commands.prompt_for_text",
        return_value=(
            "",
            False,
        ),
    ):
        result = handler(
            tmp_path,
        )

    assert result is None
    assert find_results_widget.rowCount() == 0


def test_handler_shows_message_when_no_project_is_open(
    qapp,
) -> None:
    explorer = ProjectExplorerWidget()
    find_results_widget = FindResultsWidget()
    revealed = []
    handler = create_find_in_files_handler(
        project_explorer=explorer,
        find_results_widget=find_results_widget,
        reveal_find_results=lambda: revealed.append(
            True,
        ),
    )

    with patch(
        "opencobol2.gui.search_commands.QMessageBox.information",
    ) as mock_information:
        result = handler(
            None,
        )

    mock_information.assert_called_once()
    assert result is None
    assert revealed == []


def test_handler_does_nothing_when_dialog_is_cancelled(
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
    find_results_widget = FindResultsWidget()
    revealed = []
    handler = create_find_in_files_handler(
        project_explorer=explorer,
        find_results_widget=find_results_widget,
        reveal_find_results=lambda: revealed.append(
            True,
        ),
    )

    with patch(
        "opencobol2.gui.search_commands.prompt_for_text",
        return_value=(
            "",
            False,
        ),
    ):
        result = handler(
            None,
        )

    assert result is None
    assert revealed == []
    assert find_results_widget.rowCount() == 0


def test_handler_runs_search_and_reveals_results_end_to_end(
    qapp,
    tmp_path: Path,
) -> None:
    (
        tmp_path / "main.cbl"
    ).write_text(
        "       MOVE X TO Y.\n"
    )
    project = create_project(
        name="Demo",
        root_path=tmp_path,
    )
    explorer = ProjectExplorerWidget(
        project,
    )
    find_results_widget = FindResultsWidget()
    revealed = []
    handler = create_find_in_files_handler(
        project_explorer=explorer,
        find_results_widget=find_results_widget,
        reveal_find_results=lambda: revealed.append(
            True,
        ),
    )

    with patch(
        "opencobol2.gui.search_commands.prompt_for_text",
        return_value=(
            "MOVE",
            True,
        ),
    ):
        result = handler(
            None,
        )

    assert len(result) == 1
    assert revealed == [True]
    assert find_results_widget.rowCount() == 1
    assert (
        find_results_widget.item(
            0,
            3,
        ).text()
        == "MOVE X TO Y."
    )
